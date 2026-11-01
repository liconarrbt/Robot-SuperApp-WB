#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/epoll.h>

#define MAX_EVENTS 32
#define SOCKET_PATH "/dev/socket/lmkd"

static int set_nonblocking(int fd) {
    int flags = fcntl(fd, F_GETFL, 0);
    return fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

int main(int argc, char **argv) {
    int listen_fd = -1;
    const char *env_sock = getenv("ANDROID_SOCKET_lmkd");

    if (env_sock) {
        listen_fd = atoi(env_sock);
    } else {
        unlink(SOCKET_PATH);
        listen_fd = socket(AF_UNIX, SOCK_SEQPACKET, 0);
        if (listen_fd < 0) {
            listen_fd = socket(AF_UNIX, SOCK_STREAM, 0);
        }
        struct sockaddr_un addr;
        memset(&addr, 0, sizeof(addr));
        addr.sun_family = AF_UNIX;
        strncpy(addr.sun_path, SOCKET_PATH, sizeof(addr.sun_path) - 1);
        bind(listen_fd, (struct sockaddr *)&addr, sizeof(addr));
        chmod(SOCKET_PATH, 0660);
    }

    if (listen_fd < 0) {
        perror("socket error");
        return 1;
    }

    set_nonblocking(listen_fd);
    listen(listen_fd, 16);

    int epoll_fd = epoll_create1(0);
    struct epoll_event ev, events[MAX_EVENTS];
    ev.events = EPOLLIN;
    ev.data.fd = listen_fd;
    epoll_ctl(epoll_fd, EPOLL_CTL_ADD, listen_fd, &ev);

    printf("[dummy_lmkd] Listening on lmkd socket (fd=%d)...\n", listen_fd);

    while (1) {
        int nfds = epoll_wait(epoll_fd, events, MAX_EVENTS, -1);
        if (nfds < 0) {
            if (errno == EINTR) continue;
            break;
        }

        for (int i = 0; i < nfds; i++) {
            if (events[i].data.fd == listen_fd) {
                while (1) {
                    int client = accept(listen_fd, NULL, NULL);
                    if (client < 0) break;
                    set_nonblocking(client);
                    struct epoll_event client_ev;
                    client_ev.events = EPOLLIN | EPOLLRDHUP | EPOLLHUP;
                    client_ev.data.fd = client;
                    epoll_ctl(epoll_fd, EPOLL_CTL_ADD, client, &client_ev);
                }
            } else {
                int client = events[i].data.fd;
                int32_t buf[128];
                ssize_t n = recv(client, buf, sizeof(buf), 0);
                if (n <= 0) {
                    epoll_ctl(epoll_fd, EPOLL_CTL_DEL, client, NULL);
                    close(client);
                } else if (n >= 4) {
                    int32_t cmd = buf[0];
                    if (cmd == 4) { // LMK_GETKILLCNT
                        int32_t resp[2] = { 4, 0 };
                        send(client, resp, sizeof(resp), 0);
                    }
                }
            }
        }
    }
    return 0;
}
