import os
import sys
import time
import pymem
import pymem.process
import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore
import win32api, win32con

# Mở process
pm = pymem.Pymem("ac_client.exe")
module = pymem.process.module_from_name(pm.process_handle, "ac_client.exe").lpBaseOfDll

# Player base pointer

SCREEN_WIDTH = 1600
SCREEN_HEIGHT = 900
FPS_CAPTURE = 60
MAX_PLAYERS = 10

#pointer addresses
PLAYERS_PTR_ADDR = 0x0018AC04
ME_PTR_ADDR = 0x0017E0A8
POINTER_SIZE = 0x4  # 32-bit
#offsets player
HP_OFFSET = 0xEC
BULLET_OFFSET = 0x140
BOMB_OFFSET = 0x144
NAME_OFFSET = 0x205
X_OFFSET = 0x4
Y_OFFSET = 0x8
Z_OFFSET = 0xC
TEAM_OFFSET = 0x30c

#static addresses
VIEWMATRIX_ADDR = 0x0057DFD0
PLAYER_COUNT_ADDR = 0x00591FD4

#region for aimbot
AIMBOT_REGION_WIDTH = 640
AIMBOT_REGION_HEIGHT = 640

countPlayers = pm.read_int(PLAYER_COUNT_ADDR)
teamName = {0: "CLA", 1: "RVSF"}
pMe = pm.read_int(module + ME_PTR_ADDR)
pPlayers = pm.read_int(module + PLAYERS_PTR_ADDR)
# pm.write_int(pMe + HP_OFFSET, 9999)
# pm.write_int(pMe + BULLET_OFFSET, 9999)
# pm.write_int(pMe + BOMB_OFFSET, 0)

class GameOverlay(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ESP Overlay")
        self.setGeometry(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.boxes = []
        self.texts = []

        # Timer để update overlay liên tục
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_overlay)
        self.timer.start(int(1000/FPS_CAPTURE))

    def update_overlay(self):
        self.boxes = []
        self.texts = []
        os.system("cls")
        viewMatrix = self.read_view_matrix(pm)
        countPlayers = pm.read_int(PLAYER_COUNT_ADDR)
        print(f"Count players: {countPlayers}\n")
        print("__________Duynnz__________")
        
        closestEnt = self.get_closest_entity(viewMatrix)
        if closestEnt:
            self.aimbot(closestEnt, viewMatrix)
        for i in range(countPlayers):
        # for i in range(MAX_PLAYERS):
            ent = pm.read_int(pPlayers + ((i + 1) * POINTER_SIZE))
            if ent:
                self.drawESP(ent, viewMatrix)
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Vẽ border màu đỏ cho từng khung detect
        for x, y, w, h, color in self.boxes:
            pen = QtGui.QPen(color or QtCore.Qt.red)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawRect(x, y, w, h)
        # Vẽ text
        painter.setPen(QtGui.QColor(255, 255, 255))
        for text, x, y, size in self.texts:
            font = QtGui.QFont("Arial", size)
            painter.setFont(font)
            painter.drawText(x, y, text)
    
    def world_to_screen(self, pos, view_matrix, screen_width, screen_height):
        # pos: [x, y, z]
        clip_coords = np.dot(view_matrix, np.array([pos[0], pos[1], pos[2], 1.0]))
        w = clip_coords[3]
        if w < 0.1:
            return None
        ndc = clip_coords[:3] / w  # Normalize device coordinates
        x = (screen_width / 2) * (ndc[0] + 1)
        y = (screen_height / 2) * (1 - ndc[1])
        return int(x), int(y)

    def read_view_matrix(self, pm, rotate_times=3):
        matrix = [pm.read_float(VIEWMATRIX_ADDR + i * 4) for i in range(16)]
        matrix = np.array(matrix).reshape((4, 4))
        if rotate_times > 0:
            matrix = np.rot90(matrix, rotate_times)
        return np.fliplr(matrix)
    
    def drawESP(self, ent, viewMatrix):
        try:
            xMe = pm.read_float(pMe + X_OFFSET)
            yMe = pm.read_float(pMe + Y_OFFSET)
            zMe = pm.read_float(pMe + Z_OFFSET)
            team = pm.read_int(ent + TEAM_OFFSET)
            name = pm.read_string(ent + NAME_OFFSET, 16)
            hp = pm.read_int(ent + HP_OFFSET)

            if hp <= 100 and hp > 0:
                x = pm.read_float(ent + X_OFFSET)
                y = pm.read_float(ent + Y_OFFSET)
                z = pm.read_float(ent + Z_OFFSET)
                print(f"{name:16s}: {hp:10d}, ({x:7.3f}, {y:7.3f}, {z:7.3f})")
                screen_pos = self.world_to_screen([x, y, z], viewMatrix, SCREEN_WIDTH, SCREEN_HEIGHT)
                if screen_pos:
                    [screen_x, screen_y] = screen_pos
                    distance = np.linalg.norm([x - xMe, y - yMe, z - zMe])
                    scale = distance / 100
                    size = 18
                    x, y, w, h = screen_x-(size/scale)/2, screen_y, (size/scale), 40/scale,
                    color = QtCore.Qt.blue if team == 1 else QtCore.Qt.red
                    self.boxes.append((int(x), int(y), int(w), int(h), color))
                    text = f"{name:.5} HP: {hp}"
                    font_size = int(size/scale*0.15)
                    self.texts.append((text, int(x), int(y), font_size))
        except Exception as e:
            pass
    
    def aimbot(self, ent, viewMatrix, region_width=AIMBOT_REGION_WIDTH, region_height=AIMBOT_REGION_HEIGHT):
        try:
            hp = pm.read_int(ent + HP_OFFSET)

            # Nếu nhấn chuột phải, HP không hợp lệ, hoặc cùng team => bỏ qua
            if (win32api.GetAsyncKeyState(0x02) >= 0) or not (0 <= hp <= 100):
                return

            # Lấy tọa độ world của target
            x = pm.read_float(ent + X_OFFSET)
            y = pm.read_float(ent + Y_OFFSET)
            z = pm.read_float(ent + Z_OFFSET)

            # Chuyển sang tọa độ màn hình
            screen_pos = self.world_to_screen([x, y, z], viewMatrix, SCREEN_WIDTH, SCREEN_HEIGHT)
            if not screen_pos:
                return

            target_x, target_y = screen_pos
            center_x = SCREEN_WIDTH // 2
            center_y = SCREEN_HEIGHT // 2
            half_w = region_width // 2
            half_h = region_height // 2

            # Kiểm tra xem target có nằm trong vùng mục tiêu không
            if (center_x - half_w <= target_x <= center_x + half_w and
                center_y - half_h <= target_y <= center_y + half_h):
                
                # Tính độ lệch chuột và di chuyển
                dx = target_x - center_x
                dy = target_y - center_y
                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)
                time.sleep(0.01)

        except Exception as e:
            # Bạn có thể log lỗi nếu cần
            # print("Aimbot error:", e)
            pass

    
    def get_closest_entity(
        self,
        viewMatrix,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
        max_distance=9999
    ):
        closest_ent = None
        closest_dist = max_distance

        xMe = pm.read_float(pMe + X_OFFSET)
        yMe = pm.read_float(pMe + Y_OFFSET)
        zMe = pm.read_float(pMe + Z_OFFSET)
        teamMe = pm.read_int(pMe + TEAM_OFFSET)

        countPlayers = pm.read_int(PLAYER_COUNT_ADDR)
        for i in range(countPlayers):
            ent = pm.read_int(pPlayers + ((i + 1) * POINTER_SIZE))
            if not ent:
                continue

            try:
                hp = pm.read_int(ent + HP_OFFSET)
                team = pm.read_int(ent + TEAM_OFFSET)
                if not (0 < hp <= 100) or team == teamMe:
                    continue

                # Lấy tọa độ 3D
                x = pm.read_float(ent + X_OFFSET)
                y = pm.read_float(ent + Y_OFFSET)
                z = pm.read_float(ent + Z_OFFSET)

                # Chuyển sang tọa độ 2D
                screen_pos = self.world_to_screen([x, y, z], viewMatrix, screen_width, screen_height)
                if screen_pos is None:
                    continue
                sx, sy = screen_pos
                if not (0 <= sx <= screen_width and 0 <= sy <= screen_height):
                    continue

                # Ưu tiên entity gần tâm màn hình
                dx = sx - screen_width / 2
                dy = sy - screen_height / 2
                dist = np.hypot(dx, dy)

                if dist < closest_dist:
                    closest_dist = dist
                    closest_ent = ent
            except pymem.exception.MemoryReadError:
                continue

        return closest_ent

        
app = QtWidgets.QApplication(sys.argv)
overlay = GameOverlay()
overlay.show()
sys.exit(app.exec_())

# Ma trận 1
# -0.20  -0.98   0.00  154.15      Rx    Ux    Lx    Px
# -1.74   0.36  -0.00   95.63      Ry    Uy    Ly    Py
#  0.00  -0.00  -1.00    4.20      Rz    Uz    Lz    Pz
#  0.00  -0.00  -1.00    4.50      0     0     0     1

# Ma trận 2
# -0.20  -1.74   0.00   0.00       Rx    Ry    Rz    0
# -0.98   0.36  -0.00  -0.00       Ux    Uy    Uz    0
#  0.00  -0.00  -1.00  -1.00       Lx    Ly    Lz    0
# 154.15 95.63   4.20   4.50       Px    Py    Pz    1