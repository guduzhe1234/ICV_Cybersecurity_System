"""PyCharm 直接运行：读取车载 RTSP 视频并上传云端。"""

import os
import sys


# ======================== 可修改配置 ========================
# 当前车载以太网摄像头地址。
RTSP_URL = "rtsp://192.168.4.88:8554/main"

# H.264 透传只借助 FFmpeg 做 RTSP 解包和 fMP4 封装，不做解码/编码。
FFMPEG_PATH = r"D:\ffpg\ffmpeg-8.1.1-essentials_build\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"

# copy：摄像头直接输出 H.264/H.265，程序只封装并转发原码流。
# 当前摄像头日志已确认输出 H.265（HEVC）。
VIDEO_MODE = os.getenv("VIDEO_MODE", "copy").lower()
RTSP_CODEC = os.getenv("RTSP_CODEC", "h265").lower()

# 当前 run_vehicle.py 与 run_cloud.py 运行在同一台电脑，车端数据必须走
# 本机回环，不能先经过 cpolar 再绕回本机；公网回环实测只剩约 2 FPS。
# Jetson 真车端仍在 run_vehicle_jetson.py 中使用公网 WSS 地址。
CLOUD_WS_URL = os.getenv("CLOUD_WS_URL", "ws://6dce1342.r7.nas.cpolar.cn")

VEHICLE_ID = "VHC-001"

# 必须与 run_cloud.py 中的 INGEST_TOKEN 完全一致。
INGEST_TOKEN = "vcl_687Nfse29GsoYlX0j8hPaK4ctMv_5g4nXBeYpy1Obu0"

# 透传模式下这些数值是摄像头端应配置的档位，程序不会改变原码流。
# 编码回退模式下才由程序执行缩放、限帧和码率控制。
MAX_WIDTH = int(os.getenv("VIDEO_MAX_WIDTH", "1280"))
TARGET_FPS = int(os.getenv("VIDEO_TARGET_FPS", "20"))
JPEG_QUALITY = 62
H264_BITRATE_KBPS = int(os.getenv("VIDEO_BITRATE_KBPS", "2200"))
H264_SEGMENT_MS = int(os.getenv("VIDEO_SEGMENT_MS", "1000"))

# 目标上行带宽，单位 Kbps。超过后会逐步降低 JPEG 质量。
# 设置为 0 可关闭带宽自适应。
TARGET_KBPS = 3800

# 透传模式优先实时性，只保留短 FIFO，避免断网恢复后回放很久以前的画面。
BUFFER_SECONDS = float(os.getenv(
    "VIDEO_BUFFER_SECONDS", "3" if VIDEO_MODE == "copy" else "300"
))

# 允许多张 JPEG 同时进入 TCP 发送窗口，充分利用公网带宽。
WS_WRITE_LIMIT_BYTES = 256 * 1024
MAX_FRAME_AGE_SECONDS = 10

# GNSS/CAN 适配程序持续更新的 JSON 文件。留空时不上传导航数据。
# 示例字段：latitude、longitude、speed_kph、heading_deg、accuracy_m、captured_at_ms。
NAVIGATION_FILE = os.getenv("VEHICLE_NAVIGATION_FILE", "")
# ===========================================================


def main():
    if VIDEO_MODE not in {"copy", "encode"}:
        raise SystemExit("VIDEO_MODE 只能设置为 copy 或 encode")
    if RTSP_CODEC not in {"h264", "h265"}:
        raise SystemExit("RTSP_CODEC 只能设置为 h264 或 h265")

    # 复用 vehicle_agent.py 的成熟采流、重连和上传逻辑。
    # 通过参数注入避免在 PyCharm 中手工配置运行参数。
    sys.argv = [
        sys.argv[0],
        "--source", RTSP_URL,
        "--cloud", CLOUD_WS_URL,
        "--vehicle-id", VEHICLE_ID,
        "--token", INGEST_TOKEN,
        "--width", str(MAX_WIDTH),
        "--fps", str(TARGET_FPS),
        "--bitrate-kbps", str(H264_BITRATE_KBPS),
        "--segment-ms", str(H264_SEGMENT_MS),
        "--buffer-seconds", str(BUFFER_SECONDS),
        "--send-timeout", os.getenv("VIDEO_SEND_TIMEOUT", "60"),
        "--ffmpeg", FFMPEG_PATH,
        "--encoder", "copy" if VIDEO_MODE == "copy" else "auto",
        "--rtsp-codec", RTSP_CODEC,
        "--navigation-file", NAVIGATION_FILE,
    ]

    # 需要在导入 OpenCV 之前写入低延迟参数。
    os.environ.setdefault(
        "OPENCV_FFMPEG_CAPTURE_OPTIONS",
        "rtsp_transport;tcp|stimeout;5000000",
    )

    import h264_vehicle_agent as vehicle_agent

    # Keep passthrough compatible with FFmpeg builds that expose timeout
    # options in help output but reject them for the RTSP input protocol.
    vehicle_agent.ffmpeg_rtsp_timeout_args = lambda _executable: []
    run_agent = vehicle_agent.main

    print("=" * 64)
    print("车端视频上传程序正在启动")
    print("车端版本：2026-09-11-h265-copy-v4-no-timeout")
    print("车辆编号：{}".format(VEHICLE_ID))
    print("摄像头地址：{}".format(RTSP_URL))
    print("云端地址：{}".format(CLOUD_WS_URL))
    if VIDEO_MODE == "copy":
        print("视频后端：摄像头 {} 原码流 → FFmpeg 仅封装 fMP4 → WebSocket".format(RTSP_CODEC.upper()))
        print("注意：分辨率、FPS、码率和关键帧间隔由摄像头端控制")
    else:
        print("视频后端：自动解码并重编码（兼容回退模式）")
    print(
        "视频档位：{}px / {} FPS / H.264 {} Kbps / {} ms 连续片段".format(
            MAX_WIDTH, TARGET_FPS, H264_BITRATE_KBPS, H264_SEGMENT_MS
        )
    )
    print("按 Ctrl+C 可停止车端程序")
    print("=" * 64)
    run_agent()


if __name__ == "__main__":
    main()
