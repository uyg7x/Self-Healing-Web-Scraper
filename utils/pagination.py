import asyncio
import logging
import random
import sys
import time
from urllib.parse import quote_plus

from core.config import EARLY_STOP_AFTER_EMPTY_PAGES, MAX_PAGES_PER_SITE
from .human_delay import HumanDelay
from .spinner import Spinner
from .url_utils import normalize_url, content_fingerprint

logger = logging.getLogger(__name__)


def _build_page_url(site_config: dict, query: str, page_num: int) -> str:
    pg = site_config.get("pagination", {})
    tpl = pg.get("url_template")
    if tpl:
        return tpl.replace("{query}", quote_plus(query)).replace(
            "{page}", str(page_num)
        )
    return site_config["base_search_url"].replace("{query}", quote_plus(query))


def _dedupe_into(products, seen_urls, seen_fps, out, page_num, engine_used):
    kept = 0
    for p in products:
        nurl = normalize_url(p.get("link", ""))
        fp = content_fingerprint(p)
        if nurl and nurl in seen_urls:
            continue
        if fp in seen_fps:
            continue
        if nurl:
            seen_urls.add(nurl)
        seen_fps.add(fp)
        p["page_number"] = page_num
        p["engine_used"] = engine_used
        out.append(p)
        kept += 1
    return kept


async def crawl_site(
    site_key, site_config, query, engine, antiban, healing,
    validator, delay: HumanDelay, max_pages=None, qwen=None,
):
    mode = site_config.get("crawl_mode", "url")
    max_pages = max_pages or site_config.get("pagination", {}).get(
        "max_pages", MAX_PAGES_PER_SITE
    )

    if mode == "browser":
        return await _crawl_browser(
            site_key, site_config, query, engine, healing,
            delay, max_pages, qwen,
        )
    return await _crawl_url(
        site_key, site_config, query, engine, antiban, healing,
        delay, max_pages, qwen,
    )



async def _crawl_url(
    site_key, site_config, query, engine, antiban, healing,
    delay, max_pages, qwen,
):
    seen_urls, seen_fps = set(), set()
    out = []
    empty_streak = 0
    selectors = healing.get_prioritized_selectors(site_key, site_config["selectors"])

    start = site_config.get("pagination", {}).get("start", 1)
    page_num = start
    walked = 0
    site_name = site_config["name"]

    while walked < max_pages:
        url = _build_page_url(site_config, query, page_num)


        fetch_msg = f"{site_name} p{page_num} — fetching (fast TLS)"
        async with Spinner(f"{fetch_msg}...", color="\033[96m") as s:
            html, used_engine = await antiban.fetch(
                url, site_key=site_key,
                use_browser=site_config.get("js_required", False),
            )
            if html:
                s.finish(f"{fetch_msg} — got {len(html)//1024}KB via {used_engine}")
            else:
                s.finish(f"{fetch_msg} — blocked ({used_engine})", ok=False)

        if not html:
            delay.register_failure()
            await delay.after_block()
            walked += 1
            page_num += 1
            continue

  
        extract_msg = f"{site_name} p{page_num} — extracting"
        async with Spinner(f"{extract_msg}...", color="\033[93m") as s:
            products, info = engine.extract_data(
                html, site_config["url"], selectors,
                site_config["regex_fallback"],
                site_key=site_key,
            )
            if products:
                s.finish(
                    f"{extract_msg} — {len(products)} raw via "
                    f"{info.get('method','?')}"
                )
            else:
                s.finish(f"{extract_msg} — cascade returned 0", ok=False)


        if not products and qwen is not None and getattr(qwen, "enabled", False):
            q_msg = f"{site_name} p{page_num} — Qwen fallback"
            async with Spinner(f"{q_msg}...", color="\033[95m") as s:
                qp = qwen.extract_products(html, query, target_site=site_config["url"])
                if qp:
                    products = qp
                    info = {"method": "qwen_ai_fallback", "strategy_index": -5}
                    s.finish(f"{q_msg} — recovered {len(qp)} items")
                else:
                    s.finish(f"{q_msg} — nothing", ok=False)

        if not products:
            empty_streak += 1
            logger.info(f"[{site_key}] p{page_num}: 0 products")
            if empty_streak >= EARLY_STOP_AFTER_EMPTY_PAGES:
                break
        else:
            empty_streak = 0
            kept = _dedupe_into(
                products, seen_urls, seen_fps, out, page_num, used_engine
            )
            logger.info(
                f"[{site_key}] p{page_num}: +{kept} new (total {len(out)}) "
                f"via {info.get('method','?')}"
            )
            healing.record_success(
                site_key, info.get("strategy_index", 0),
                info.get("method", "unknown"),
            )
            delay.register_success()
            print(
                f"   \033[92m +{kept} new\033[0m "
                f"(total {len(out)}) via {info.get('method','?')}"
            )

        walked += 1
        page_num += 1
        if walked < max_pages:
            d = await _spinner_delay(delay, site_name, page_num)
            logger.debug(f"[{site_key}] slept {d:.1f}s")

    return out




async def _crawl_browser(
    site_key, site_config, query, engine, healing,
    delay, max_pages, qwen,
):
    try:
        from camoufox.async_api import AsyncCamoufox
    except ImportError:
        logger.error(f"[{site_key}] camoufox not installed")
        return []

    from .profile_manager import has_profile, profile_path

    seen_urls, seen_fps = set(), set()
    out = []
    selectors = healing.get_prioritized_selectors(site_key, site_config["selectors"])
    site_name = site_config["name"]

    kwargs = {
        "headless": True,
        "os": "windows",
        "geoip": True,
        "humanize": True,
    }
    if has_profile(site_key):
        kwargs["persistent_context"] = True
        kwargs["user_data_dir"] = str(profile_path(site_key))
        logger.info(f"[{site_key}] using saved profile")
    else:
        logger.info(f"[{site_key}] no profile - running fresh")

    try:
        async with AsyncCamoufox(**kwargs) as ctx:
            if kwargs.get("persistent_context"):
                page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            else:
                context = await ctx.new_context()
                page = await context.new_page()

  

            async with Spinner(
                f"{site_name} - pre-flight warm-up...", color="\033[95m"
            ) as s:
                try:
                    await page.goto(
                        "https://www.google.com",
                        wait_until="domcontentloaded", timeout=15000,
                    )
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                    s.finish(f"{site_name} - warm-up complete")
                except Exception as e:
                    s.finish(f"{site_name} - warm-up skipped ({e})", ok=False)



            search_url = site_config["base_search_url"].replace(
                "{query}", quote_plus(query)
            )
            nav_msg = f"{site_name} - loading search page"
            async with Spinner(f"{nav_msg}...", color="\033[96m") as s:
                t0 = time.time()
                try:
                    await page.goto(
                        search_url, wait_until="domcontentloaded", timeout=30000
                    )
                    load_t = time.time() - t0
                    s.finish(f"{nav_msg} - loaded in {load_t:.1f}s")
                except Exception as e:
                    s.finish(f"{nav_msg} - failed ({e})", ok=False)
                    delay.register_failure()
                    return []
            await delay.page_load(time.time() - t0)

            next_sel = site_config.get("next_selector")
            page_num = 1
            empty_streak = 0
            walked = 0

 
 
 
            while walked < max_pages:

                for _ in range(random.randint(2, 4)):
                    try:
                        await page.evaluate(
                            f"window.scrollBy(0, {random.randint(300, 700)})"
                        )
                    except Exception:
                        pass
                    await delay.scroll_pause()



                grab_msg = f"{site_name} p{page_num} - reading DOM"
                async with Spinner(f"{grab_msg}...", color="\033[95m") as s:
                    try:
                        html = await page.content()
                        s.finish(f"{grab_msg} - {len(html)//1024}KB")
                    except Exception as e:
                        s.finish(f"{grab_msg} - failed ({e})", ok=False)
                        delay.register_failure()
                        break



                extract_msg = f"{site_name} p{page_num} - extracting"
                async with Spinner(f"{extract_msg}...", color="\033[93m") as s:
                    products, info = engine.extract_data(
                        html, site_config["url"],
                        selectors, site_config["regex_fallback"],
                        site_key=site_key,
                    )
                    if products:
                        s.finish(
                            f"{extract_msg} - {len(products)} raw via "
                            f"{info.get('method','?')}"
                        )
                    else:
                        s.finish(f"{extract_msg} - cascade returned 0", ok=False)



                if (
                    not products
                    and qwen is not None
                    and getattr(qwen, "enabled", False)
                ):
                    q_msg = f"{site_name} p{page_num} - Qwen fallback"
                    async with Spinner(f"{q_msg}...", color="\033[95m") as s:
                        qp = qwen.extract_products(
                            html, query, target_site=site_config["url"]
                        )
                        if qp:
                            products = qp
                            info = {
                                "method": "qwen_ai_fallback",
                                "strategy_index": -5,
                            }
                            s.finish(f"{q_msg} - recovered {len(qp)} items")
                        else:
                            s.finish(f"{q_msg} - nothing", ok=False)

                if not products:
                    empty_streak += 1
                    logger.info(f"[{site_key}] p{page_num}: 0 products")
                    if empty_streak >= EARLY_STOP_AFTER_EMPTY_PAGES:
                        break
                else:
                    empty_streak = 0
                    kept = _dedupe_into(
                        products, seen_urls, seen_fps, out, page_num, "camoufox"
                    )
                    logger.info(
                        f"[{site_key}] p{page_num}: +{kept} new "
                        f"(total {len(out)}) via {info.get('method','?')}"
                    )
                    healing.record_success(
                        site_key, info.get("strategy_index", 0),
                        info.get("method", "unknown"),
                    )
                    delay.register_success()
                    print(
                        f"   \033[92m +{kept} new\033[0m "
                        f"(total {len(out)}) via {info.get('method','?')}"
                    )

                walked += 1
                page_num += 1
                if walked >= max_pages:
                    break

                if not next_sel:
                    logger.info(f"[{site_key}] no next_selector - stopping")
                    break

                await _spinner_delay(delay, site_name, page_num)

    
    
    
    

                click_msg = (
                    f"{site_name} p{page_num-1} -> p{page_num} - clicking next"
                )
                advanced = False
                t0 = time.time()

                async with Spinner(f"{click_msg}...", color="\033[96m") as s:
                    try:
                        btn = await page.wait_for_selector(
                            next_sel, timeout=5000, state="attached"
                        )
                        if btn is not None:
                            await btn.scroll_into_view_if_needed()
                            await delay.micro_pause()
                            t0 = time.time()
                            await btn.click()
                            await page.wait_for_load_state(
                                "domcontentloaded", timeout=20000
                            )
                            load_t = time.time() - t0
                            s.finish(f"{click_msg} - loaded in {load_t:.1f}s")
                            advanced = True
                    except Exception as e:
                        s.finish(
                            f"{click_msg} - click failed, trying URL", ok=False
                        )




                if not advanced:
                    tpl = site_config.get("pagination", {}).get("url_template")
                    if tpl:
                        next_url = tpl.replace(
                            "{query}", quote_plus(query)
                        ).replace("{page}", str(page_num))
                        fb_msg = f"{site_name} p{page_num} - URL fallback"
                        async with Spinner(f"{fb_msg}...", color="\033[93m") as s:
                            try:
                                t0 = time.time()
                                await page.goto(
                                    next_url,
                                    wait_until="domcontentloaded",
                                    timeout=25000,
                                )
                                load_t = time.time() - t0
                                s.finish(f"{fb_msg} - loaded in {load_t:.1f}s")
                                advanced = True
                            except Exception as e:
                                s.finish(f"{fb_msg} - failed ({e})", ok=False)

                if not advanced:
                    logger.info(
                        f"[{site_key}] cannot advance - stopping at p{page_num-1}"
                    )
                    break

                await delay.page_load(time.time() - t0)

    except Exception as e:
        logger.error(f"[{site_key}] browser session crashed: {e}")
        delay.register_failure()

    return out




async def _spinner_delay(
    delay: HumanDelay, site_name: str, next_page: int
) -> float:
  
    target = delay._sample()
    if random.random() < delay.long_pause_chance:
        target += random.uniform(*delay.long_pause_range)

    if delay.page_count + 1 >= delay.next_break_at:
        target += random.uniform(*delay.coffee_duration)
        tag = "coffee break"
    elif delay.failure_count > 0:
        target += min((2 ** delay.failure_count) * 5, 120.0)
        tag = "backoff"
    else:
        tag = "reading"

    target = min(target, delay.hard_max)
    start = time.time()
    stop_event = asyncio.Event()

    async def _tick():
        while not stop_event.is_set():
            elapsed = time.time() - start
            remain = max(0.0, target - elapsed)
            sys.stdout.write(
                f"\r\033[2m   {tag} {site_name} -> p{next_page} in "
                f"{remain:5.1f}s  [{tag}]\033[0m"
            )
            sys.stdout.flush()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.1)
            except asyncio.TimeoutError:
                pass
        sys.stdout.write("\r" + " " * 70 + "\r")
        sys.stdout.flush()

    task = asyncio.create_task(_tick())
    try:
        await asyncio.sleep(target)
    finally:
        stop_event.set()
        try:
            await task
        except Exception:
            pass


    delay.page_count += 1
    if delay.page_count >= delay.next_break_at:
        delay.next_break_at = delay.page_count + random.randint(
            *delay.coffee_break_range
        )
    return target
