/**
 * @file yolo_camera.cpp
 * @brief 独立 YOLO 检测程序 - 模型 + 摄像头 + MJPEG 实时推流
 *
 * 用法: ./yolo_camera <engine_path> [camera_id] [threshold] [nms_threshold]
 * 示例: ./yolo_camera /path/to/model.engine 0 0.25 0.45
 * 浏览器打开 http://<jetson_ip>:8080 查看实时画面
 * 终端按 Ctrl+C 退出
 */

#include <iostream>
#include <chrono>
#include <thread>
#include <mutex>
#include <vector>
#include <sstream>
#include <csignal>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <opencv2/opencv.hpp>
#include "dvision/yolo/yolo26.hpp"

using namespace dvision;
using namespace std;

static volatile sig_atomic_t g_running = 1;
static void sig_handler(int) { g_running = 0; }

// MJPEG 流服务器（简单单线程 TCP server）
class MjpegServer {
public:
    MjpegServer(int port) : port_(port) {}

    bool start() {
        // 非阻塞检查端口是否可用
        server_fd_ = socket(AF_INET, SOCK_STREAM, 0);
        if (server_fd_ < 0) return false;

        int opt = 1;
        setsockopt(server_fd_, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = INADDR_ANY;
        addr.sin_port = htons(port_);

        if (bind(server_fd_, (sockaddr*)&addr, sizeof(addr)) < 0) {
            close(server_fd_); return false;
        }
        if (listen(server_fd_, 4) < 0) {
            close(server_fd_); return false;
        }
        thread_ = thread(&MjpegServer::run, this);
        return true;
    }

    void updateFrame(const cv::Mat& frame) {
        vector<uchar> buf;
        cv::imencode(".jpg", frame, buf, {cv::IMWRITE_JPEG_QUALITY, 70});
        lock_guard<mutex> lk(mtx_);
        jpeg_buf_.swap(buf);
    }

    void stop() {
        g_running = 0;
        close(server_fd_);
        if (thread_.joinable()) thread_.join();
    }

private:
    void run() {
        while (g_running) {
            fd_set fds;
            FD_ZERO(&fds);
            FD_SET(server_fd_, &fds);
            timeval tv{1, 0};
            if (select(server_fd_ + 1, &fds, nullptr, nullptr, &tv) <= 0) continue;

            int client = accept(server_fd_, nullptr, nullptr);
            if (client < 0) continue;
            handleClient(client);
        }
    }

    void handleClient(int client) {
        // 读 HTTP 请求头
        char buf[4096];
        int n = recv(client, buf, sizeof(buf) - 1, 0);
        if (n <= 0) { close(client); return; }
        buf[n] = '\0';

        // 只处理 GET 请求
        if (strncmp(buf, "GET ", 4) != 0) {
            httpError(client, 400); return;
        }

        // 发送 MJPEG 头
        string header =
            "HTTP/1.0 200 OK\r\n"
            "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: close\r\n"
            "\r\n";
        send(client, header.c_str(), header.size(), MSG_NOSIGNAL);

        while (g_running) {
            vector<uchar> jpeg;
            {
                lock_guard<mutex> lk(mtx_);
                jpeg = jpeg_buf_;
            }
            if (jpeg.empty()) {
                this_thread::sleep_for(chrono::milliseconds(10));
                continue;
            }

            ostringstream part;
            part << "--frame\r\n"
                 << "Content-Type: image/jpeg\r\n"
                 << "Content-Length: " << jpeg.size() << "\r\n"
                 << "\r\n";
            string part_str = part.str();

            if (send(client, part_str.c_str(), part_str.size(), MSG_NOSIGNAL) < 0) break;
            if (send(client, jpeg.data(), jpeg.size(), MSG_NOSIGNAL) < 0) break;
            if (send(client, "\r\n", 2, MSG_NOSIGNAL) < 0) break;

            this_thread::sleep_for(chrono::milliseconds(40)); // ~25fps
        }
        close(client);
    }

    void httpError(int client, int code) {
        string msg = "HTTP/1.0 " + to_string(code) + " OK\r\n\r\n";
        send(client, msg.c_str(), msg.size(), MSG_NOSIGNAL);
        close(client);
    }

    int port_, server_fd_ = -1;
    thread thread_;
    mutex mtx_;
    vector<uchar> jpeg_buf_;
};

int main(int argc, char* argv[]) {
    if (argc < 2) {
        cerr << "用法: " << argv[0] << " <engine_path> [camera_id] [threshold] [nms_threshold]" << endl;
        cerr << "示例: " << argv[0] << " /path/to/model.engine 0 0.25 0.45" << endl;
        cerr << "浏览器打开 http://<ip>:8080 查看实时画面" << endl;
        return 1;
    }

    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);

    string engine_path = argv[1];
    int camera_id      = (argc >= 3) ? stoi(argv[2]) : 0;
    float threshold     = (argc >= 4) ? stof(argv[3]) : 0.25f;
    float nms_threshold = (argc >= 5) ? stof(argv[4]) : 0.45f;

    cout << "================================" << endl;
    cout << "  YOLO 摄像头实时检测" << endl;
    cout << "================================" << endl;
    cout << "  模型:     " << engine_path << endl;
    cout << "  摄像头:   " << camera_id << endl;
    cout << "  阈值:     " << threshold << endl;
    cout << "  NMS阈值:  " << nms_threshold << endl;
    cout << "  MJPEG:    http://0.0.0.0:8080" << endl;
    cout << "================================" << endl;

    // 初始化检测器（参数对齐生产环境 object_detector.cpp:53-57）
    yolo26 detector;
    try {
        cout << "正在加载模型..." << flush;
        detector.init(engine_path, threshold, nms_threshold, 1, 736, 1280,
                      Yolo26Config::CLASS_NUM, 300);
        cout << " 成功!" << endl;
    } catch (const exception& e) {
        cerr << "模型加载失败: " << e.what() << endl;
        return 1;
    }

    // 打开摄像头
    cv::VideoCapture cap(camera_id);
    if (!cap.isOpened()) {
        cerr << "错误：无法打开摄像头 " << camera_id << "！" << endl;
        return 1;
    }

    // 启动 MJPEG 服务器
    MjpegServer mjpeg(8080);
    if (!mjpeg.start()) {
        cerr << "警告：MJPEG 服务器启动失败，仅打印检测结果" << endl;
    }

    cv::Mat frame;
    int frame_count = 0;
    float fps = 0;
    auto last_fps_time = chrono::steady_clock::now();

    while (g_running && cap.read(frame)) {
        if (frame.empty()) continue;

        auto t0 = chrono::steady_clock::now();

        // 执行检测
        auto detections = detector.detect(frame);

        auto t1 = chrono::steady_clock::now();
        float infer_ms = chrono::duration<float, milli>(t1 - t0).count();

        // 绘制检测框
        for (const auto& det : detections) {
            float cx = det.bbox[0], cy = det.bbox[1];
            float w  = det.bbox[2], h  = det.bbox[3];
            float x1 = max(0.0f, cx - w / 2);
            float y1 = max(0.0f, cy - h / 2);
            float x2 = min((float)frame.cols, cx + w / 2);
            float y2 = min((float)frame.rows, cy + h / 2);

            cv::rectangle(frame, cv::Point(x1, y1), cv::Point(x2, y2),
                         cv::Scalar(0, 255, 0), 2);
            cv::putText(frame,
                       cv::format("cls%d %.2f", (int)det.class_id, det.conf),
                       cv::Point(x1, y1 - 5),
                       cv::FONT_HERSHEY_SIMPLEX, 0.4, cv::Scalar(0, 255, 0), 1);
        }

        // FPS
        frame_count++;
        float elapsed = chrono::duration<float>(chrono::steady_clock::now() - last_fps_time).count();
        if (elapsed >= 1.0f) {
            fps = frame_count / elapsed;
            frame_count = 0;
            last_fps_time = chrono::steady_clock::now();
            cout << "FPS: " << fps << " | 推理: " << infer_ms << "ms | 检出: "
                 << detections.size() << endl;
        }

        // HUD
        cv::putText(frame,
                   cv::format("FPS:%.1f Infer:%.1fms Objs:%zu", fps, infer_ms, detections.size()),
                   cv::Point(10, 25),
                   cv::FONT_HERSHEY_SIMPLEX, 0.6, cv::Scalar(0, 255, 255), 2);

        mjpeg.updateFrame(frame);
    }

    mjpeg.stop();
    cap.release();
    cout << "程序退出。" << endl;
    return 0;
}
