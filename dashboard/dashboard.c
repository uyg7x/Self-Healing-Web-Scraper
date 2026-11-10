#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <ctype.h>
#include <winsock2.h>
#include <windows.h>

#define PORT            8080
#define MAX_CSV_LINE    4096
#define MAX_HTML_SIZE   (64 * 1024 * 1024)
#define MAX_COLS        20
#define MAX_TD_BYTES    10000


void html_escape(const char *src, char *dest, size_t dest_size) {
    size_t j = 0;
    for (size_t i = 0; src[i] != '\0' && j < dest_size - 1; i++) {
        switch (src[i]) {
            case '&':  if (j + 5 < dest_size) { memcpy(dest + j, "&amp;", 5); j += 5; } break;
            case '<':  if (j + 4 < dest_size) { memcpy(dest + j, "&lt;", 4); j += 4; } break;
            case '>':  if (j + 4 < dest_size) { memcpy(dest + j, "&gt;", 4); j += 4; } break;
            case '"':  if (j + 6 < dest_size) { memcpy(dest + j, "&quot;", 6); j += 6; } break;
            case '\'': if (j + 6 < dest_size) { memcpy(dest + j, "&#39;", 6); j += 6; } break;
            default:   dest[j++] = src[i]; break;
        }
    }
    dest[j] = '\0';
}


void url_decode(char *src, char *dest) {
    int i = 0, j = 0;
    char hex[3] = {0};
    while (src[i]) {
        if (src[i] == '%' && isxdigit((unsigned char)src[i+1]) && isxdigit((unsigned char)src[i+2])) {
            hex[0] = src[i+1]; hex[1] = src[i+2];
            dest[j++] = (char)strtol(hex, NULL, 16);
            i += 3;
        } else if (src[i] == '+') {
            dest[j++] = ' ';
            i++;
        } else {
            dest[j++] = src[i++];
        }
    }
    dest[j] = '\0';
}


int parse_csv_line(char *line, char *cols[], int max_cols) {
    int col_count = 0;
    int in_quotes = 0;
    char *write = line;
    int i = 0;

    line[strcspn(line, "\r\n")] = 0;
    cols[0] = line;

    while (line[i] && col_count < max_cols - 1) {
        char c = line[i];
        if (c == '"') {
            if (in_quotes && line[i + 1] == '"') {
                if (write != &line[i]) *write = '"';
                write++;
                i += 2;
                continue;
            }
            in_quotes = !in_quotes;
            i++;
            continue;
        }
        if (c == ',' && !in_quotes) {
            *write = '\0';
            col_count++;
            cols[col_count] = write + 1;
            write++;
            i++;
            continue;
        }
        if (write != &line[i]) *write = c;
        write++;
        i++;
    }
    *write = '\0';

    if (col_count < max_cols) col_count++;
    return col_count;
}


void parse_requested_file(const char *url, char *filename) {
    filename[0] = '\0';
    const char *file_param = strstr(url, "file=");
    if (file_param) {
        file_param += 5;
        int i = 0;
        char raw_name[256] = {0};

        while (file_param[i] && file_param[i] != '&' && file_param[i] != ' ' && i < 255) {
            raw_name[i] = file_param[i];
            i++;
        }
        raw_name[i] = '\0';

        url_decode(raw_name, filename);

        if (strstr(filename, "..") || strchr(filename, '/') || strchr(filename, '\\')) {
            filename[0] = '\0';
            return;
        }

        int len = strlen(filename);
        if (len < 4 || strcmp(filename + len - 4, ".csv") != 0) {
            filename[0] = '\0';
        }
    }
}


static void append_classic_head(char *html, const char *title) {
    char safe_title[512];
    html_escape(title, safe_title, sizeof(safe_title));

    strncat(html, "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>", MAX_HTML_SIZE - strlen(html) - 1);
    strncat(html, safe_title, MAX_HTML_SIZE - strlen(html) - 1);
    strncat(html,
      "</title><style>"
      "*{box-sizing:border-box;} html,body{margin:0;padding:0;height:100%;}"
      "body{background:#008080;font-family:'MS Sans Serif',Tahoma,Verdana,sans-serif;font-size:11px;color:#000;padding:8px;}"
      ".window{background:#c0c0c0;max-width:1400px;margin:0 auto;padding:3px;border:2px solid;border-color:#dfdfdf #000000 #000000 #dfdfdf;box-shadow:2px 2px 0 #00000033;}"
      ".titlebar{display:flex;justify-content:space-between;align-items:center;padding:2px 3px;font-weight:bold;font-size:11px;color:#ffffff;user-select:none;background:linear-gradient(90deg,#000080 0%,#1084d0 50%,#000080 100%);border:1px solid #dfdfdf;}"
      ".titlebar-title{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-left:2px;text-shadow:1px 1px 1px #00000055;}"
      ".window-body{background:#c0c0c0;padding:6px;}"
      ".panel{background:#ffffff;padding:2px;border:2px solid;border-color:#808080 #ffffff #ffffff #808080;box-shadow:1px 1px 0 #dfdfdf inset;}"
      ".btn{display:inline-block;min-width:75px;padding:3px 10px;background:#c0c0c0;color:#000;text-decoration:none;text-align:center;font-family:'MS Sans Serif',Tahoma,sans-serif;font-size:11px;cursor:pointer;user-select:none;margin:0;border:2px solid;border-color:#ffffff #000000 #000000 #ffffff;}"
      ".btn:active{border-color:#000000 #ffffff #ffffff #000000;padding:4px 9px 2px 11px;}"
      ".file-list{list-style:none;margin:0;padding:0;background:#ffffff;}"
      ".file-list li{border-bottom:1px solid #dfdfdf;}.file-list li:last-child{border-bottom:none;}"
      ".file-list a{display:block;padding:4px 6px;color:#000000;text-decoration:none;font-size:11px;}"
      ".file-list a:hover{background:#000080;color:#ffffff;}"
      ".file-list a:before{content:'\\1F4C4  ';}"
      "table{width:100%;border-collapse:collapse;background:#ffffff;font-size:11px;border:2px solid;border-color:#808080 #ffffff #ffffff #808080;}"
      "th,td{padding:2px 4px;text-align:left;border:1px solid #c0c0c0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:340px;}"
      "th{position:sticky;top:0;font-weight:bold;background:#c0c0c0;border:2px solid;border-color:#ffffff #808080 #808080 #ffffff;padding:3px 4px;}"
      "tr:nth-child(even) td{background:#f0f0f0;}tr:nth-child(odd) td{background:#ffffff;}"
      "tbody tr:hover td{background:#000080;color:#ffffff;}"
      "td.price{color:#800000;font-weight:bold;}tbody tr:hover td.price{color:#ff8080;}"
      ".statusbar{display:flex;gap:1px;margin-top:4px;font-size:11px;border-top:2px solid #dfdfdf;padding-top:2px;}"
      ".statusbar span{flex:1;padding:2px 4px;background:#c0c0c0;border:1px solid;border-color:#808080 #ffffff #ffffff #808080;}"
      ".toolbar{display:flex;gap:6px;align-items:center;flex-wrap:wrap;padding:4px 6px;background:#c0c0c0;border:2px solid;border-color:#dfdfdf #000000 #000000 #dfdfdf;margin-bottom:6px;font-size:11px;}"
      ".toolbar input[type=text],.toolbar input[type=number]{font-family:'MS Sans Serif',Tahoma,sans-serif;font-size:11px;padding:2px 4px;border:2px solid;border-color:#808080 #ffffff #ffffff #808080;background:#ffffff;color:#000;}"
      ".toolbar input[type=text]{width:240px;}"
      ".toolbar input[type=number]{width:90px;}"
      ".toolbar button{min-width:auto;padding:3px 10px;background:#c0c0c0;color:#000;font-family:'MS Sans Serif',Tahoma,sans-serif;font-size:11px;cursor:pointer;border:2px solid;border-color:#ffffff #000000 #000000 #ffffff;}"
      ".toolbar button:active{border-color:#000000 #ffffff #ffffff #000000;padding:4px 9px 2px 11px;}"
      ".toolbar .sep{width:1px;height:20px;background:#808080;margin:0 4px;}"
      ".toolbar label{font-size:11px;white-space:nowrap;}"
      ".row-count{margin-left:auto;padding:2px 8px;background:#f0f0f0;border:1px solid;border-color:#808080 #ffffff #ffffff #808080;font-family:'MS Sans Serif',Tahoma,sans-serif;font-size:11px;white-space:nowrap;}"
      "th.sortable{cursor:pointer;user-select:none;}"
      "th.sortable:hover{background:#d0d0d0;}"
      "th.sort-asc::after{content:' \\25B2';color:#000080;font-size:10px;}"
      "th.sort-desc::after{content:' \\25BC';color:#000080;font-size:10px;}"
      "</style></head><body>", MAX_HTML_SIZE - strlen(html) - 1);
}


char* generate_file_menu(void) {
    char *html = (char *)calloc(1, MAX_HTML_SIZE);
    if (!html) return NULL;

    append_classic_head(html, "File Explorer");

    strncat(html,
      "<div class='window'><div class='titlebar'>"
      "<span class='titlebar-title'>\xF0\x9F\x93\x81 File Explorer - data\\</span>"
      "</div><div class='window-body'><p style='margin:0 0 6px 0;'>Select a CSV file to view:</p>"
      "<div class='panel'><ul class='file-list'>",
      MAX_HTML_SIZE - strlen(html) - 1);

    WIN32_FIND_DATA ffd;
    HANDLE hFind = FindFirstFile("data/*.csv", &ffd);
    if (hFind == INVALID_HANDLE_VALUE) {
        strncat(html, "<li><a href='#'>No CSV files found in data\\</a></li>", MAX_HTML_SIZE - strlen(html) - 1);
    } else {
        do {
            if (!(ffd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) {
                char safe_name[256];
                html_escape(ffd.cFileName, safe_name, sizeof(safe_name));
                char item[600];
                snprintf(item, sizeof(item), "<li><a href='/view?file=%s'>%s</a></li>", safe_name, safe_name);
                strncat(html, item, MAX_HTML_SIZE - strlen(html) - 1);
            }
        } while (FindNextFile(hFind, &ffd));
        FindClose(hFind);
    }

    strncat(html,
      "</ul></div><div class='statusbar'><span>Ready</span><span>data\\*.csv</span></div>"
      "</div></div></body></html>",
      MAX_HTML_SIZE - strlen(html) - 1);
    return html;
}


char* generate_csv_table(const char *filename) {
    char filepath[512];
    snprintf(filepath, sizeof(filepath), "data/%s", filename);

    FILE *file = fopen(filepath, "r");
    if (!file) {
        char *err = (char *)calloc(1, MAX_HTML_SIZE);
        if (!err) return NULL;
        append_classic_head(err, "Error");
        char safe_name[256];
        html_escape(filename, safe_name, sizeof(safe_name));
        char err_body[1024];
        snprintf(err_body, sizeof(err_body),
          "<div class='window'><div class='titlebar'><span class='titlebar-title'>Error</span></div>"
          "<div class='window-body'><p style='color:#a00;font-weight:bold;'>\xE2\x9A\xA0 File not found: %s</p>"
          "<a href='/' class='btn'>Back</a></div></div></body></html>", safe_name);
        strncat(err, err_body, MAX_HTML_SIZE - strlen(err) - 1);
        return err;
    }

    char *html = (char *)calloc(1, MAX_HTML_SIZE);
    if (!html) { fclose(file); return NULL; }

    append_classic_head(html, "Viewing Data");

    char safe_filename[256];
    html_escape(filename, safe_filename, sizeof(safe_filename));

    char open_html[1400];
    snprintf(open_html, sizeof(open_html),
      "<div class='window'><div class='titlebar'>"
      "<span class='titlebar-title'>\xF0\x9F\x93\x8A %s</span></div>"
      "<div class='window-body'>"
      "<div class='toolbar'>"
      "<a href='/' class='btn'>\xE2\xAC\x85 Back</a>"
      "<span class='sep'></span>"
      "<label>\xF0\x9F\x94\x8D</label>"
      "<input type='text' id='searchBox' placeholder='Search products, brands, URLs...'>"
      "<span class='sep'></span>"
      "<label>Price \xE2\x82\xB9</label>"
      "<input type='number' id='minPrice' placeholder='min' min='0' step='100'>"
      "<label>\xE2\x80\x93</label>"
      "<input type='number' id='maxPrice' placeholder='max' min='0' step='100'>"
      "<button type='button' id='clearBtn'>Clear</button>"
      "<span class='row-count' id='rowCount'>\xE2\x80\xA6</span>"
      "</div>"
      "<div class='panel' style='overflow:auto;max-height:calc(100vh - 170px);'>"
      "<table id='dataTable'><thead><tr>", safe_filename);
    strncat(html, open_html, MAX_HTML_SIZE - strlen(html) - 1);

        char line[MAX_CSV_LINE];
    int row_count = 0, is_header = 1;
    int price_col_idx = -1, link_col_idx = -1, image_col_idx = -1;
    int source_col_idx = -1;

    while (fgets(line, sizeof(line), file)) {
        char *cols[MAX_COLS];
        int col_count = parse_csv_line(line, cols, MAX_COLS);

                if (is_header) {
            int rendered_idx = 0;
            for (int i = 0; i < col_count && i < MAX_COLS; i++) {
                if (strstr(cols[i], "Image") != NULL) { image_col_idx = i; continue; }
                if (strcmp(cols[i], "Source") == 0) { source_col_idx = i; continue; }
                if (strstr(cols[i], "Price") != NULL && price_col_idx == -1) price_col_idx = i;
                if (strstr(cols[i], "Link") != NULL && link_col_idx == -1) link_col_idx = i;

                const char *type_str = "text";
                if (i == price_col_idx) type_str = "price";
                else if (strstr(cols[i], "Score") != NULL) type_str = "number";
                else if (i == link_col_idx) type_str = "url";

                char safe_col[1024];
                html_escape(cols[i], safe_col, sizeof(safe_col));

                char th[1500];
                snprintf(th, sizeof(th),
                  "<th class='sortable' data-col='%d' data-type='%s'>%s</th>",
                  rendered_idx, type_str, safe_col);
                strncat(html, th, MAX_HTML_SIZE - strlen(html) - 1);
                rendered_idx++;
            }
            strncat(html, "</tr></thead><tbody>", MAX_HTML_SIZE - strlen(html) - 1);
            is_header = 0;
        } else {
                        strncat(html, "<tr>", MAX_HTML_SIZE - strlen(html) - 1);
            int rendered_idx = 0;
            for (int i = 0; i < col_count; i++) {
                if (i == image_col_idx) continue;
                if (i == source_col_idx) continue;
                char safe_col[4096];
                html_escape(cols[i], safe_col, sizeof(safe_col));

                char td[MAX_TD_BYTES];

                if (i == price_col_idx) {
                    snprintf(td, sizeof(td),
                      "<td data-col='%d' class='price'>%s</td>",
                      rendered_idx, safe_col);
                } else if (i == link_col_idx && strstr(safe_col, "http") != NULL) {
                    snprintf(td, sizeof(td),
                      "<td data-col='%d' data-href='%s'>"
                      "<a href='%s' target='_blank'>\xF0\x9F\x94\x97 Open Link</a></td>",
                      rendered_idx, safe_col, safe_col);
                } else if (strstr(safe_col, "http") == safe_col) {
                    snprintf(td, sizeof(td),
                      "<td data-col='%d' data-href='%s'>"
                      "<a href='%s' target='_blank'>\xF0\x9F\x94\x97 Open Link</a></td>",
                      rendered_idx, safe_col, safe_col);
                } else {
                    snprintf(td, sizeof(td),
                      "<td data-col='%d'>%s</td>", rendered_idx, safe_col);
                }
                strncat(html, td, MAX_HTML_SIZE - strlen(html) - 1);
                rendered_idx++;
            }
            strncat(html, "</tr>", MAX_HTML_SIZE - strlen(html) - 1);
            row_count++;
        }
    }
    fclose(file);

    if (is_header) {
        strncat(html, "</tr></thead><tbody>", MAX_HTML_SIZE - strlen(html) - 1);
    }

    char footer[768];
    snprintf(footer, sizeof(footer),
      "</tbody></table></div>"
      "<div class='statusbar'><span id='statusRows'>%d rows</span><span>%s</span><span>Ready</span></div>"
      "</div></div>", row_count, safe_filename);
    strncat(html, footer, MAX_HTML_SIZE - strlen(html) - 1);

  
    strncat(html,
      "<script>(function(){'use strict';"
      "var searchBox=document.getElementById('searchBox');"
      "var minPriceInput=document.getElementById('minPrice');"
      "var maxPriceInput=document.getElementById('maxPrice');"
      "var clearBtn=document.getElementById('clearBtn');"
      "var rowCountEl=document.getElementById('rowCount');"
      "var statusRowsEl=document.getElementById('statusRows');"
      "var tbody=document.querySelector('#dataTable tbody');"
      "if(!tbody)return;"
      "var headers=Array.prototype.slice.call(document.querySelectorAll('#dataTable thead th'));"

      "var PRICE_COL=-1;"
      "headers.forEach(function(th){"
      "  if(th.dataset.type==='price'&&PRICE_COL<0)PRICE_COL=parseInt(th.dataset.col);"
      "});"

      "function parseNumber(txt){"
      "  var cleaned=txt.replace(/[\\u20B9$\\u00A3,]/g,'').replace(/[^0-9.\\-]/g,'');"
      "  var m=cleaned.match(/-?[0-9]+(?:\\.[0-9]+)?/);"
      "  return m?parseFloat(m[0]):-1;"
      "}"

      "function getCellValue(tr,colIdx,type){"
      "  var td=tr.querySelector('td[data-col=\"'+colIdx+'\"]');"
      "  if(!td)return'';"
      "  var txt=td.textContent.trim();"
      "  if(type==='price'||type==='number')return parseNumber(txt);"
      "  return txt.toLowerCase();"
      "}"

      "var sortCol=-1,sortDir=1;"

      "function sortTable(colIdx){"
      "  if(sortCol===colIdx){sortDir=-sortDir;}else{sortCol=colIdx;sortDir=1;}"
      "  var th=null;"
      "  headers.forEach(function(h){if(parseInt(h.dataset.col)===colIdx)th=h;});"
      "  if(!th)return;"
      "  var type=th.dataset.type||'text';"
      "  headers.forEach(function(h){h.classList.remove('sort-asc','sort-desc');});"
      "  th.classList.add(sortDir>0?'sort-asc':'sort-desc');"
      "  var rows=Array.prototype.slice.call(tbody.querySelectorAll('tr'));"
      "  rows.sort(function(a,b){"
      "    var av=getCellValue(a,colIdx,type);"
      "    var bv=getCellValue(b,colIdx,type);"
      "    var aInvalid=(type==='price'||type==='number')&&(typeof av!=='number'||av<0);"
      "    var bInvalid=(type==='price'||type==='number')&&(typeof bv!=='number'||bv<0);"
      "    if(aInvalid&&bInvalid)return 0;"
      "    if(aInvalid)return 1;"
      "    if(bInvalid)return -1;"
      "    if(typeof av==='number'&&typeof bv==='number')return(av-bv)*sortDir;"
      "    return String(av).localeCompare(String(bv))*sortDir;"
      "  });"
      "  rows.forEach(function(r){tbody.appendChild(r);});"
      "  applyFilters();"
      "}"

      "headers.forEach(function(th){"
      "  if(th.classList.contains('sortable')){"
      "    th.addEventListener('click',function(){sortTable(parseInt(th.dataset.col));});"
      "  }"
      "});"

      "function applyFilters(){"
      "  var term=(searchBox.value||'').toLowerCase().trim();"
      "  var minV=parseFloat(minPriceInput.value);"
      "  var maxV=parseFloat(maxPriceInput.value);"
      "  var minP=isNaN(minV)?-Infinity:minV;"
      "  var maxP=isNaN(maxV)?Infinity:maxV;"
      "  var usePrice=PRICE_COL>=0&&(minP>-Infinity||maxP<Infinity);"
      "  var rows=tbody.querySelectorAll('tr');"
      "  var visible=0;"
      "  Array.prototype.forEach.call(rows,function(tr){"
      "    var match=true;"
      "    if(term){"
      "      var txt=tr.textContent.toLowerCase();"
      "      var hrefs=tr.querySelectorAll('td[data-href]');"
      "      Array.prototype.forEach.call(hrefs,function(td){"
      "        txt+=' '+(td.dataset.href||'').toLowerCase();"
      "      });"
      "      match=txt.indexOf(term)!==-1;"
      "    }"
      "    if(match&&usePrice){"
      "      var pv=getCellValue(tr,PRICE_COL,'price');"
      "      if(typeof pv!=='number'||pv<0){match=false;}"
      "      else{match=pv>=minP&&pv<=maxP;}"
      "    }"
      "    tr.style.display=match?'':'none';"
      "    if(match)visible++;"
      "  });"
      "  var total=rows.length;"
      "  var s=visible+' of '+total+' rows';"
      "  rowCountEl.textContent=s;"
      "  if(statusRowsEl)statusRowsEl.textContent=s;"
      "}"

      "searchBox.addEventListener('input',applyFilters);"
      "minPriceInput.addEventListener('input',applyFilters);"
      "maxPriceInput.addEventListener('input',applyFilters);"

      "clearBtn.addEventListener('click',function(){"
      "  searchBox.value='';"
      "  minPriceInput.value='';"
      "  maxPriceInput.value='';"
      "  headers.forEach(function(h){h.classList.remove('sort-asc','sort-desc');});"
      "  sortCol=-1;sortDir=1;"
      "  applyFilters();"
      "});"

      "applyFilters();"
      "})();</script>",
      MAX_HTML_SIZE - strlen(html) - 1);

    strncat(html, "</body></html>", MAX_HTML_SIZE - strlen(html) - 1);

    return html;
}


int main(void) {
    char exePath[MAX_PATH];
    GetModuleFileNameA(NULL, exePath, MAX_PATH);
    char *slash = strrchr(exePath, '\\');
    if (slash) *slash = '\0';
    slash = strrchr(exePath, '\\');
    if (slash) *slash = '\0';
    SetCurrentDirectoryA(exePath);

    WSADATA wsaData;
    SOCKET serverSocket, clientSocket;
    struct sockaddr_in serverAddr, clientAddr;
    int addrLen = sizeof(clientAddr);
    char buffer[2048];

    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
        printf("Winsock failed!\n");
        return 1;
    }

    serverSocket = socket(AF_INET, SOCK_STREAM, 0);
    serverAddr.sin_family = AF_INET;
    serverAddr.sin_addr.s_addr = inet_addr("127.0.0.1");
    serverAddr.sin_port = htons(PORT);

    bind(serverSocket, (struct sockaddr*)&serverAddr, sizeof(serverAddr));
    listen(serverSocket, 5);

    printf("==================================================\n");
    printf("  C Dashboard Server is running\n");
    printf("  Open: http://127.0.0.1:%d\n", PORT);
    printf("==================================================\n");

    while (1) {
        clientSocket = accept(serverSocket, (struct sockaddr*)&clientAddr, &addrLen);
        if (clientSocket == INVALID_SOCKET) continue;

        int bytes_received = recv(clientSocket, buffer, sizeof(buffer) - 1, 0);
        if (bytes_received <= 0) { closesocket(clientSocket); continue; }
        buffer[bytes_received] = '\0';

        char method[10] = {0}, url[512] = {0}, version[10] = {0};
        sscanf(buffer, "%9s %511s %9s", method, url, version);

        char *html_content = NULL;
        int status_code = 200;

        if (strcmp(url, "/") == 0 || strcmp(url, "/index.html") == 0) {
            html_content = generate_file_menu();
        } else if (strncmp(url, "/view", 5) == 0) {
            char filename[256];
            parse_requested_file(url, filename);
            if (filename[0]) {
                html_content = generate_csv_table(filename);
            } else {
                html_content = _strdup("<h2>400 Bad Request: Invalid file.</h2>");
                status_code = 400;
            }
        } else {
            html_content = _strdup("<h2>404 Not Found</h2>");
            status_code = 404;
        }

        if (html_content) {
            char http_header[512];
            const char *status_text = (status_code == 200) ? "OK" : (status_code == 404) ? "Not Found" : "Bad Request";
            snprintf(http_header, sizeof(http_header),
                "HTTP/1.1 %d %s\r\n"
                "Content-Type: text/html; charset=UTF-8\r\n"
                "Content-Length: %zu\r\n"
                "Connection: close\r\n\r\n",
                status_code, status_text, strlen(html_content));

            send(clientSocket, http_header, (int)strlen(http_header), 0);
            send(clientSocket, html_content, (int)strlen(html_content), 0);
            free(html_content);
        }

        closesocket(clientSocket);
    }

    closesocket(serverSocket);
    WSACleanup();
    return 0;
}