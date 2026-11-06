#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <winsock2.h>
#include <windows.h>

#define PORT            8080
#define MAX_CSV_LINE    4096
#define MAX_HTML_SIZE   2000000
#define MAX_COLS        20

/* ============================================================
 *  CSV parser (unchanged)
 * ============================================================ */
int parse_csv_line(char *line, char *cols[], int max_cols) {
    int col_count = 0;
    int in_quotes = 0;
    char *start = line;
    int i = 0;

    line[strcspn(line, "\r\n")] = 0;

    while (line[i] && col_count < max_cols) {
        if (line[i] == '"') {
            in_quotes = !in_quotes;
            if (col_count == 0 && i == 0) start = &line[i + 1];
        } else if (line[i] == ',' && !in_quotes) {
            line[i] = '\0';
            cols[col_count++] = start;
            start = &line[i + 1];
            if (*start == '"') start++;
        }
        i++;
    }
    if (col_count < max_cols) {
        cols[col_count++] = start;
        int len = strlen(cols[col_count - 1]);
        if (len > 0 && cols[col_count - 1][len - 1] == '"') {
            cols[col_count - 1][len - 1] = '\0';
        }
    }
    return col_count;
}

/* ============================================================
 *  URL query parsing (unchanged)
 * ============================================================ */
void parse_requested_file(const char *url, char *filename) {
    filename[0] = '\0';
    const char *file_param = strstr(url, "file=");
    if (file_param) {
        file_param += 5;
        int i = 0;
        while (file_param[i] && file_param[i] != '&' && file_param[i] != ' ' && i < 255) {
            filename[i] = file_param[i];
            i++;
        }
        filename[i] = '\0';
        if (i < 4 || strcmp(filename + i - 4, ".csv") != 0) {
            filename[0] = '\0';
        }
    }
}

/* ============================================================
 *  Shared classic-Windows CSS + chrome header (UPDATED - No Taskbar CSS)
 * ============================================================ */
static void append_classic_head(char *html, const char *title) {
    strcat(html, "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>");
    strcat(html, title);
    strcat(html,
      "</title><style>"
      "*{box-sizing:border-box;} html,body{margin:0;padding:0;height:100%;}"
      "body{"
        "background:#008080;"
        "font-family:'MS Sans Serif',Tahoma,Verdana,sans-serif;"
        "font-size:11px;color:#000;"
        "padding:8px;"
      "}"

      /* ---- Window Chrome (Classic 3D Bevel) ---- */
      ".window{background:#c0c0c0;max-width:1400px;margin:0 auto;padding:3px;"
        "border:2px solid;border-color:#dfdfdf #000000 #000000 #dfdfdf;"
        "box-shadow:2px 2px 0 #00000033;}"
      ".titlebar{display:flex;justify-content:space-between;align-items:center;"
        "padding:2px 3px;font-weight:bold;font-size:11px;color:#ffffff;"
        "user-select:none;"
        "background:linear-gradient(90deg,#000080 0%,#1084d0 50%,#000080 100%);"
        "border:1px solid #dfdfdf;"
      "}"
      ".titlebar-title{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
        "padding-left:2px;text-shadow:1px 1px 1px #00000055;}"

      ".window-body{background:#c0c0c0;padding:6px;}"

      /* ---- Sunken Panel (Like Win95 Listbox/Edit Field) ---- */
      ".panel{background:#ffffff;padding:2px;"
        "border:2px solid;border-color:#808080 #ffffff #ffffff #808080;"
        "box-shadow:1px 1px 0 #dfdfdf inset;}"

      /* ---- Classic Windows Buttons ---- */
      ".btn{display:inline-block;min-width:75px;padding:3px 10px;"
        "background:#c0c0c0;color:#000;text-decoration:none;text-align:center;"
        "font-family:'MS Sans Serif',Tahoma,sans-serif;font-size:11px;"
        "cursor:pointer;user-select:none;margin:2px;"
        "border:2px solid;border-color:#ffffff #000000 #000000 #ffffff;}"
      ".btn:active{border-color:#000000 #ffffff #ffffff #000000;"
        "padding:4px 9px 2px 11px;}"
      ".btn:focus{outline:1px dotted #000;outline-offset:-3px;}"

      /* ---- File List ---- */
      ".file-list{list-style:none;margin:0;padding:0;background:#ffffff;}"
      ".file-list li{border-bottom:1px solid #dfdfdf;}"
      ".file-list li:last-child{border-bottom:none;}"
      ".file-list a{display:block;padding:4px 6px;color:#000000;"
        "text-decoration:none;font-size:11px;}"
      ".file-list a:hover{background:#000080;color:#ffffff;}"
      ".file-list a:before{content:'\\1F4C4  ';}"

      /* ---- Data Table (Classic Win95 Listview) ---- */
      "table{width:100%;border-collapse:collapse;background:#ffffff;font-size:11px;"
        "border:2px solid;border-color:#808080 #ffffff #ffffff #808080;}"
      "th,td{padding:2px 4px;text-align:left;border:1px solid #c0c0c0;"
        "white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}"
      "th{position:sticky;top:0;font-weight:bold;background:#c0c0c0;"
        "border:2px solid;border-color:#ffffff #808080 #808080 #ffffff;"
        "padding:3px 4px;}"
      "tr:nth-child(even) td{background:#f0f0f0;}"
      "tr:nth-child(odd) td{background:#ffffff;}"
      "tbody tr:hover td{background:#000080;color:#ffffff;}"
      "td.price{color:#800000;font-weight:bold;}"
      "tbody tr:hover td.price{color:#ff8080;}"

      /* ---- Status Bar ---- */
      ".statusbar{display:flex;gap:1px;margin-top:4px;font-size:11px;"
        "border-top:2px solid #dfdfdf;padding-top:2px;}"
      ".statusbar span{flex:1;padding:2px 4px;background:#c0c0c0;"
        "border:1px solid;border-color:#808080 #ffffff #ffffff #808080;}"
      
      "</style></head><body>");
}

/* ============================================================
 *  Page 1: file picker (NO TASKBAR, NO TITLE BAR BUTTONS)
 * ============================================================ */
char* generate_file_menu(void) {
    char *html = (char *)malloc(MAX_HTML_SIZE);
    if (!html) return NULL;
    html[0] = '\0';

    append_classic_head(html, "File Explorer");

    strcat(html,
        "<div class='window'>"
          "<div class='titlebar'>"
            "<span class='titlebar-title'>\xF0\x9F\x93\x81 File Explorer - data\\</span>"
          "</div>"
          "<div class='window-body'>"
            "<p style='margin:0 0 6px 0;'>Select a CSV file to view:</p>"
            "<div class='panel'><ul class='file-list'>");

    WIN32_FIND_DATA ffd;
    HANDLE hFind = FindFirstFile("data/*.csv", &ffd);
    if (hFind == INVALID_HANDLE_VALUE) {
        strcat(html, "<li><a href='#'>No CSV files found in data\\</a></li>");
    } else {
        do {
            if (!(ffd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) {
                char item[1024];
                snprintf(item, sizeof(item),
                    "<li><a href='/view?file=%s'>%s</a></li>",
                    ffd.cFileName, ffd.cFileName);
                strcat(html, item);
            }
        } while (FindNextFile(hFind, &ffd));
        FindClose(hFind);
    }

    strcat(html,
            "</ul></div>"
            "<div class='statusbar'>"
              "<span>Ready</span>"
              "<span>data\\*.csv</span>"
            "</div>"
          "</div>"
        "</div>"
        "</body></html>");
    
    return html;
}

/* ============================================================
 *  Page 2: CSV table view (NO TASKBAR, NO TITLE BAR BUTTONS)
 * ============================================================ */
char* generate_csv_table(const char *filename) {
    char filepath[512];
    snprintf(filepath, sizeof(filepath), "data/%s", filename);

    FILE *file = fopen(filepath, "r");
    if (!file) {
        char *err = (char *)malloc(MAX_HTML_SIZE);
        if (!err) return NULL;
        err[0] = '\0';
        append_classic_head(err, "Error");
        strcat(err,
            "<div class='window'>"
              "<div class='titlebar'><span class='titlebar-title'>Error</span></div>"
              "<div class='window-body'>"
                "<p style='color:#a00;font-weight:bold;'>\xE2\x9A\xA0 File not found: ");
        strcat(err, filename);
        strcat(err, "</p><a href='/' class='btn'>Back</a></div></div>"
        "</body></html>");
        return err;
    }

    char *html = (char *)malloc(MAX_HTML_SIZE);
    if (!html) { fclose(file); return NULL; }
    html[0] = '\0';

    append_classic_head(html, "Viewing Data");

    strcat(html,
        "<div class='window'>"
          "<div class='titlebar'>"
            "<span class='titlebar-title'>\xF0\x9F\x93\x8A ");
    strcat(html, filename);
    strcat(html, "</span></div>"
          "<div class='window-body'>"
            "<div style='margin-bottom:6px;'>"
              "<a href='/' class='btn'>\xE2\x86\x90 Back</a>"
            "</div>"
            "<div class='panel' style='overflow:auto;max-height:calc(100vh - 120px);'>"
              "<table><thead><tr>");

    char line[MAX_CSV_LINE];
    int row_count = 0, is_header = 1;
    int price_col_idx = -1, link_col_idx = -1, image_col_idx = -1;

    while (fgets(line, sizeof(line), file)) {
        char *cols[MAX_COLS];
        int col_count = parse_csv_line(line, cols, MAX_COLS);

        if (is_header) {
            for (int i = 0; i < col_count && i < MAX_COLS; i++) {
                if (strstr(cols[i], "Image") != NULL) { image_col_idx = i; continue; }
                char th[256];
                snprintf(th, sizeof(th), "<th>%s</th>", cols[i]);
                strcat(html, th);
                if (strstr(cols[i], "Price") != NULL && price_col_idx == -1) price_col_idx = i;
                if (strstr(cols[i], "Link")  != NULL && link_col_idx  == -1) link_col_idx  = i;
            }
            strcat(html, "</tr></thead><tbody>");
            is_header = 0;
        } else {
            strcat(html, "<tr>");
            for (int i = 0; i < col_count; i++) {
                if (i == image_col_idx) continue;

                char td[2048];
                if (i == price_col_idx) {
                    snprintf(td, sizeof(td), "<td class='price'>%s</td>", cols[i]);
                } else if ((i == link_col_idx || strstr(cols[i], "http") == cols[i])
                           && strstr(cols[i], "http") != NULL) {
                    snprintf(td, sizeof(td),
                        "<td><a href='%s' target='_blank'>\xF0\x9F\x94\x97 Link</a></td>",
                        cols[i]);
                } else {
                    snprintf(td, sizeof(td), "<td>%s</td>", cols[i]);
                }
                strcat(html, td);
            }
            strcat(html, "</tr>");
            row_count++;
        }
    }
    fclose(file);

    char footer[768];
    snprintf(footer, sizeof(footer),
        "</tbody></table></div>"
        "<div class='statusbar'>"
          "<span>%d rows</span>"
          "<span>%s</span>"
          "<span>Ready</span>"
        "</div>"
      "</div></div>"
      "</body></html>",
      row_count, filename);
    strcat(html, footer);

    return html;
}

/* ============================================================
 *  HTTP server (unchanged)
 * ============================================================ */
int main(void) {
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
    serverAddr.sin_addr.s_addr = INADDR_ANY;
    serverAddr.sin_port = htons(PORT);

    bind(serverSocket, (struct sockaddr*)&serverAddr, sizeof(serverAddr));
    listen(serverSocket, 5);

    printf("==================================================\n");
    printf("  C Dashboard Server is running\n");
    printf("  Open: http://localhost:%d\n", PORT);
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

        if (strcmp(url, "/") == 0 || strcmp(url, "/index.html") == 0) {
            html_content = generate_file_menu();
        } else if (strncmp(url, "/view", 5) == 0) {
            char filename[256];
            parse_requested_file(url, filename);
            if (filename[0]) html_content = generate_csv_table(filename);
            else             html_content = strdup("<h2>Invalid file requested.</h2>");
        } else {
            html_content = strdup("<h2>404 Not Found</h2>");
        }

        if (html_content) {
            char http_header[512];
            snprintf(http_header, sizeof(http_header),
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/html; charset=UTF-8\r\n"
                "Content-Length: %zu\r\n"
                "Connection: close\r\n\r\n",
                strlen(html_content));
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