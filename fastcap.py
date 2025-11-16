import sys
import time
import os
import tempfile
import subprocess
from dataclasses import dataclass, field
import numpy as np
import pyautogui
import wave
import ctypes
from ctypes import wintypes
try:
    import sounddevice as sd
except Exception:
    sd = None

try:
    from imageio_ffmpeg import get_ffmpeg_exe
    _ffmpeg_exe = None
    _base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    try:
        _dirs = [os.path.join(_base, "imageio_ffmpeg"), _base]
        for _d in _dirs:
            if os.path.isdir(_d):
                for _name in os.listdir(_d):
                    _n = _name.lower()
                    if _n.startswith("ffmpeg") and _n.endswith(".exe"):
                        _p = os.path.join(_d, _name)
                        if os.path.exists(_p):
                            _ffmpeg_exe = _p
                            break
            if _ffmpeg_exe:
                break
    except Exception:
        _ffmpeg_exe = None
    if _ffmpeg_exe is None:
        try:
            _ffmpeg_exe = get_ffmpeg_exe()
        except Exception:
            _ffmpeg_exe = None
    if _ffmpeg_exe and os.path.exists(_ffmpeg_exe):
        os.environ["IMAGEIO_FFMPEG_EXE"] = _ffmpeg_exe
except Exception:
    pass

from PySide6.QtCore import Qt, QRect, QPoint, QRectF, QPointF, Signal, QThread, QTimer, QAbstractNativeEventFilter
from PySide6.QtGui import (
    QAction,
    QColor,
    QGuiApplication,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QKeySequence,
    QShortcut,
    QFont,
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QSystemTrayIcon,
    QMenu,
    QFileDialog,
    QToolBar,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsPathItem,
    QGraphicsTextItem,
    QGraphicsItem,
    QMessageBox,
    QLabel,
    QComboBox,
)

import mss
try:
    import cv2
except Exception:
    cv2 = None


# ----- Utilities -----

def create_app_icon() -> QIcon:
    # Simple in-memory icon to avoid external resources
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(44, 143, 255))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 4, 56, 56, 12, 12)
    p.setPen(QPen(QColor(255, 255, 255), 5))
    p.drawLine(18, 20, 46, 20)
    p.drawLine(18, 33, 46, 33)
    p.drawLine(18, 46, 40, 46)
    p.end()
    return QIcon(pix)


 


def capture_all_monitors() -> QPixmap:
    # 优先使用 MSS 抓取整个虚拟桌面（物理像素级），确保清晰度不受 DPI 缩放影响
    try:
        with mss.mss() as sct:
            mon = sct.monitors[0]
            shot = sct.grab(mon)
            qimg = QImage(shot.rgb, shot.width, shot.height, QImage.Format_RGB888)
            qimg = qimg.copy()
            pix = QPixmap.fromImage(qimg)
            try:
                screens = QGuiApplication.screens()
                if screens:
                    union = screens[0].geometry()
                    for s in screens[1:]:
                        union = union.united(s.geometry())
                    dpr_w = shot.width / max(1, union.width())
                    dpr_h = shot.height / max(1, union.height())
                    dpr = max(1.0, (dpr_w + dpr_h) / 2.0)
                    # 限制极端值，但保持高分辨率
                    if dpr > 4.0:
                        dpr = 4.0
                    pix.setDevicePixelRatio(dpr)
            except Exception:
                pass
            return pix
    except Exception:
        pass

def _cursor_hide():
    try:
        QGuiApplication.setOverrideCursor(Qt.BlankCursor)
    except Exception:
        pass
    try:
        for _ in range(8):
            if ctypes.windll.user32.ShowCursor(False) < 0:
                break
    except Exception:
        pass

def _cursor_show():
    try:
        QGuiApplication.restoreOverrideCursor()
    except Exception:
        pass

def _move_mouse_outside_rect(rect: QRect):
    try:
        union = None
        try:
            screens = QGuiApplication.screens()
            if screens:
                union = screens[0].geometry()
                for s in screens[1:]:
                    union = union.united(s.geometry())
        except Exception:
            union = QRect(0, 0, max(1, rect.right() + 200), max(1, rect.bottom() + 200))
        tx, ty = union.left() + 5, union.top() + 5
        if rect.contains(QPoint(tx, ty)):
            tx = union.right() - 5
            ty = union.bottom() - 5
        try:
            pyautogui.FAILSAFE = False
            pyautogui.moveTo(tx, ty)
        except Exception:
            pass
    except Exception:
        pass
    try:
        for _ in range(8):
            if ctypes.windll.user32.ShowCursor(True) >= 0:
                break
    except Exception:
        pass

    # 回退：使用 Qt 抓屏并按最高 DPI 合成高分辨率图像
    try:
        screens = QGuiApplication.screens()
        if screens:
            union = screens[0].geometry()
            for s in screens[1:]:
                union = union.united(s.geometry())
            # 计算各屏抓取的像素比，选取较高者作为输出 DPR
            dprs = []
            pix_per_screen = []
            for s in screens:
                p = s.grabWindow(0)
                dprs.append(float(getattr(p, 'devicePixelRatio', lambda: 1.0)()))
                pix_per_screen.append(p)
            base_dpr = max([1.0] + dprs)
            img = QImage(int(union.width() * base_dpr), int(union.height() * base_dpr), QImage.Format_ARGB32)
            try:
                img.setDevicePixelRatio(base_dpr)
            except Exception:
                pass
            img.fill(Qt.transparent)
            painter = QPainter(img)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
            origin = union.topLeft()
            # 将绘制坐标按 base_dpr 缩放，保证物理像素级合成
            painter.scale(base_dpr, base_dpr)
            for s, p in zip(screens, pix_per_screen):
                g = s.geometry()
                painter.drawPixmap(g.topLeft() - origin, p)
            painter.end()
            return QPixmap.fromImage(img)
    except Exception:
        pass
    # 若仍失败，返回一个空白图避免崩溃
    empty = QPixmap(1, 1)
    empty.fill(Qt.transparent)
    return empty


def capture_all_monitors_overlay() -> QPixmap:
    """用于选区叠加层的抓屏：严格按 Qt 逻辑坐标合成，保证 1:1 显示不放大。
    - 逐屏使用 Qt 的 grabWindow 抓取；
    - 在一个以虚拟桌面“逻辑尺寸”(DIP) 创建的 QImage 上绘制；
    - 禁用平滑变换，避免柔化；
    """
    try:
        screens = QGuiApplication.screens()
        if not screens:
            return QPixmap()
        union = screens[0].geometry()
        for s in screens[1:]:
            union = union.united(s.geometry())
        # 选择一个较高的 DPR 作为画布，保证清晰度（取各屏最大 DPR）
        dprs = []
        pix_per_screen = []
        for s in screens:
            p = s.grabWindow(0)
            pix_per_screen.append(p)
            try:
                dprs.append(float(getattr(p, 'devicePixelRatio', lambda: 1.0)()))
            except Exception:
                dprs.append(1.0)
        base_dpr = max([1.0] + dprs)
        if base_dpr > 4.0:
            base_dpr = 4.0
        img = QImage(int(union.width() * base_dpr), int(union.height() * base_dpr), QImage.Format_ARGB32)
        try:
            img.setDevicePixelRatio(base_dpr)
        except Exception:
            pass
        img.fill(Qt.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        origin = union.topLeft()
        # 不做额外缩放，直接按逻辑坐标绘制；Qt 会按各自 DPR 正确映射
        for s, p in zip(screens, pix_per_screen):
            g = s.geometry()
            painter.drawPixmap(g.topLeft() - origin, p)
        painter.end()
        return QPixmap.fromImage(img)
    except Exception:
        pass
    # 回退到通用路径（可能造成 DPI 误差，但不崩溃）
    return capture_all_monitors()


def capture_region(rect: QRect) -> QPixmap:
    # 优先使用 Qt 原生抓屏（与选择坐标体系一致，大小与普通截图一致）
    try:
        pt = rect.center()
        screen = QGuiApplication.screenAt(pt)
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        pix = screen.grabWindow(0, rect.left(), rect.top(), rect.width(), rect.height())
        if not pix.isNull():
            return pix
    except Exception:
        pass
    # 回退到 MSS 捕获（少数环境 Qt 抓屏失败时）
    with mss.mss() as sct:
        bbox = {
            "left": rect.left(),
            "top": rect.top(),
            "width": rect.width(),
            "height": rect.height(),
        }
        shot = sct.grab(bbox)
        qimg = QImage(shot.rgb, shot.width, shot.height, QImage.Format_RGB888)
        qimg = qimg.copy()
        pix = QPixmap.fromImage(qimg)
        return pix


def _wheel_scroll(delta: int):
    try:
        WM_MOUSEWHEEL = 0x020A
        POINT = wintypes.POINT
        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        hwnd = ctypes.windll.user32.WindowFromPoint(pt)
        if hwnd:
            wparam = (ctypes.c_uint16(0).value) | (ctypes.c_int16(delta).value << 16)
            lparam = (pt.y << 16) | (pt.x & 0xFFFF)
            ctypes.windll.user32.SendMessageW(hwnd, WM_MOUSEWHEEL, wparam, lparam)
            return
        ctypes.windll.user32.mouse_event(0x0800, 0, 0, int(delta), 0)
    except Exception:
        try:
            pyautogui.scroll(int(delta / 120))
        except Exception:
            pass

# ----- Selection Overlay -----

class SelectionOverlay(QMainWindow):
    captured = Signal(QPixmap)
    captured_rect = Signal(QRect)

    def __init__(self, base_pixmap: QPixmap):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.base_pixmap = base_pixmap
        self._selecting = False
        self._start = QPoint()
        self._end = QPoint()

        # Cover the virtual desktop
        union = self._virtual_desktop_rect()
        self.setGeometry(union)

        # Ensure mouse tracking for preview
        self.setMouseTracking(True)

    def _virtual_desktop_rect(self) -> QRect:
        screens = QGuiApplication.screens()
        if not screens:
            return QRect(0, 0, self.base_pixmap.width(), self.base_pixmap.height())
        rect = screens[0].geometry()
        for s in screens[1:]:
            rect = rect.united(s.geometry())
        return rect

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_Right):
            self.close()
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._selecting = True
            self._start = event.globalPosition().toPoint()
            self._end = self._start
            self.update()
        elif event.button() == Qt.RightButton:
            self.close()

    def mouseMoveEvent(self, event):
        if self._selecting:
            self._end = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._selecting:
            self._selecting = False
            rect = QRect(self._start, self._end).normalized()
            if rect.width() > 2 and rect.height() > 2:
                # Crop from base_pixmap using desktop coords
                # Note: base_pixmap assumed aligned to virtual desktop origin
                # If differing origins, MSS region capture is more robust:
                cropped = capture_region(rect)
                self.captured.emit(cropped)
                self.captured_rect.emit(rect)
            self.close()

    def paintEvent(self, event):
        p = QPainter(self)
        # 背景位图不做平滑缩放，保持像素清晰；矢量仅在边框处抗锯齿
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.setRenderHint(QPainter.Antialiasing, True)

        # Draw captured desktop
        p.drawPixmap(0, 0, self.base_pixmap)
        # Draw overlay using mask subtraction to avoid scaling mismatch
        if self._selecting:
            rect = QRect(self.mapFromGlobal(self._start), self.mapFromGlobal(self._end)).normalized()
            path = QPainterPath()
            path.setFillRule(Qt.OddEvenFill)
            path.addRect(QRectF(self.rect()))
            path.addRect(QRectF(rect))
            p.fillPath(path, QColor(0, 0, 0, 120))
            p.setPen(QPen(QColor(255, 85, 0), 2, Qt.SolidLine))
            p.drawRect(rect)
        else:
            p.fillRect(self.rect(), QColor(0, 0, 0, 120))


# ----- Editor -----

@dataclass
class ToolState:
    tool: str = "none"  # none | rect | arrow | text | brush
    color: QColor = field(default_factory=lambda: QColor(255, 0, 0))
    width: int = 3
    font_size: float = 14.0


class EditorView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, tool_state: ToolState):
        super().__init__(scene)
        self.tool_state = tool_state
        # 仅启用矢量抗锯齿，禁用位图平滑以保持像素级清晰
        self.setRenderHints(QPainter.Antialiasing)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._current_item = None
        self._start_pos = None
        self._items_stack = []  # for undo
        self._tag_counter = 1

    def _pen(self) -> QPen:
        return QPen(self.tool_state.color, self.tool_state.width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

    def mousePressEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        if event.button() == Qt.LeftButton:
            self._start_pos = scene_pos
            tool = self.tool_state.tool
            # 命中检测：避免点击已有文本框或其手柄时创建新文本
            item_under = self.itemAt(event.pos())
            try:
                if tool in ("rect", "arrow", "brush") and item_under is not None:
                    if isinstance(item_under, MoveHandleItem):
                        try:
                            item_under.parent_text.setSelected(True)
                        except Exception:
                            pass
                        try:
                            event.accept()
                        except Exception:
                            pass
                        return
                    if isinstance(item_under, (ResizableTextItem, TagItem, QGraphicsRectItem, QGraphicsPathItem)):
                        try:
                            item_under.setSelected(True)
                        except Exception:
                            pass
                        try:
                            event.accept()
                        except Exception:
                            pass
                        return
            except Exception:
                pass
            if tool == "rect":
                item = QGraphicsRectItem(QRectF(scene_pos, scene_pos))
                item.setPen(self._pen())
                item.setBrush(Qt.transparent)
                try:
                    item.setFlags(QGraphicsItem.ItemIsSelectable)
                except Exception:
                    pass
                self.scene().addItem(item)
                self._current_item = item
            elif tool == "arrow":
                path = QPainterPath(scene_pos)
                path.lineTo(scene_pos)
                item = QGraphicsPathItem(path)
                item.setPen(self._pen())
                try:
                    item.setFlags(QGraphicsItem.ItemIsSelectable)
                except Exception:
                    pass
                self.scene().addItem(item)
                self._current_item = item
            elif tool == "brush":
                # 显式设置起点，避免后续 lineTo 默认从 (0,0) 开始
                path = QPainterPath()
                path.moveTo(scene_pos)
                item = QGraphicsPathItem(path)
                item.setPen(self._pen())
                try:
                    item.setFlags(QGraphicsItem.ItemIsSelectable)
                except Exception:
                    pass
                self.scene().addItem(item)
                self._current_item = item
            elif tool == "text":
                from typing import Optional
                exists_hit = False
                try:
                    from PySide6.QtWidgets import QGraphicsTextItem as _QtTextItem
                    if item_under is not None:
                        # 命中已有文本或其调整手柄，进入移动/编辑，不创建新文本
                        if isinstance(item_under, (ResizableTextItem, _QtTextItem, MoveHandleItem)):
                            exists_hit = True
                            try:
                                item_under.setSelected(True)
                            except Exception:
                                pass
                except Exception:
                    pass
                if not exists_hit:
                    text_item = ResizableTextItem("文字", self.tool_state.color)
                    try:
                        f = QFont()
                        f.setPointSizeF(float(self.tool_state.font_size))
                        text_item.setFont(f)
                    except Exception:
                        pass
                    text_item.setPos(scene_pos)
                    self.scene().addItem(text_item)
                    self._items_stack.append(text_item)
            elif tool == "tag":
                # 标签工具：
                # - 点击标签：只选中，不创建
                # - 点击其他编辑项（文本、矩形、箭头/画笔、拖动按钮）：只选中，不创建
                # - 点击底图或空白：创建新标签
                handled = False
                try:
                    if item_under is not None:
                        from PySide6.QtWidgets import QGraphicsPixmapItem as _Pix
                        if isinstance(item_under, TagItem):
                            handled = True
                            try:
                                item_under.setSelected(True)
                            except Exception:
                                pass
                        elif isinstance(item_under, (ResizableTextItem, MoveHandleItem, QGraphicsRectItem, QGraphicsPathItem)):
                            handled = True
                            try:
                                item_under.setSelected(True)
                            except Exception:
                                pass
                        elif isinstance(item_under, _Pix):
                            handled = False  # 在底图上点击视为空白，创建标签
                except Exception:
                    pass
                if not handled:
                    item = TagItem(int(self._tag_counter), self.tool_state.color)
                    item.setPos(scene_pos)
                    self.scene().addItem(item)
                    self._items_stack.append(item)
                    self._tag_counter += 1
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._current_item is None:
            super().mouseMoveEvent(event)
            return
        scene_pos = self.mapToScene(event.pos())
        tool = self.tool_state.tool
        if tool == "rect":
            rect = QRectF(self._start_pos, scene_pos).normalized()
            self._current_item.setRect(rect)
        elif tool == "brush":
            path = self._current_item.path()
            # 若路径为空，确保先移动到起点
            try:
                if path.isEmpty():
                    path.moveTo(self._start_pos)
            except Exception:
                pass
            path.lineTo(scene_pos)
            self._current_item.setPath(path)
        elif tool == "arrow":
            # Build a line with triangular head
            path = QPainterPath(self._start_pos)
            path.lineTo(scene_pos)
            # arrowhead
            vec = scene_pos - self._start_pos
            length = (vec.x() ** 2 + vec.y() ** 2) ** 0.5
            if length > 1:
                # unit vector
                ux, uy = vec.x() / length, vec.y() / length
                head_len = 10 + self.tool_state.width * 1.5
                head_width = 6 + self.tool_state.width
                # perpendicular
                px, py = -uy, ux
                tip = scene_pos
                left = QPointF(tip.x() - ux * head_len + px * head_width, tip.y() - uy * head_len + py * head_width)
                right = QPointF(tip.x() - ux * head_len - px * head_width, tip.y() - uy * head_len - py * head_width)
                path.moveTo(left)
                path.lineTo(tip)
                path.lineTo(right)
            self._current_item.setPath(path)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._current_item is not None and event.button() == Qt.LeftButton:
            self._items_stack.append(self._current_item)
            self._current_item = None
        super().mouseReleaseEvent(event)

    def undo(self):
        if not self._items_stack:
            return
        item = self._items_stack.pop()
        self.scene().removeItem(item)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            deleted_any = False
            deleted_tag_nums = []
            try:
                selected = list(self.scene().selectedItems())
            except Exception:
                selected = []
            for it in selected:
                try:
                    if (
                        isinstance(it, ResizableTextItem)
                        or isinstance(it, TagItem)
                        or isinstance(it, QGraphicsRectItem)
                        or isinstance(it, QGraphicsPathItem)
                    ):
                        try:
                            if bool(it.textInteractionFlags() & Qt.TextEditorInteraction):
                                continue
                        except Exception:
                            pass
                        try:
                            if isinstance(it, TagItem):
                                deleted_tag_nums.append(int(getattr(it, "number", 0)))
                        except Exception:
                            pass
                        self.scene().removeItem(it)
                        try:
                            if it in self._items_stack:
                                self._items_stack = [x for x in self._items_stack if x is not it]
                        except Exception:
                            pass
                        deleted_any = True
                except Exception:
                    pass
            if deleted_tag_nums:
                try:
                    tags = [i for i in self.scene().items() if isinstance(i, TagItem)]
                    try:
                        tags.sort(key=lambda t: int(getattr(t, "number", 0)))
                    except Exception:
                        pass
                    idx = 1
                    for t in tags:
                        try:
                            t.number = int(idx)
                            idx += 1
                            try:
                                t.update()
                            except Exception:
                                pass
                        except Exception:
                            pass
                    try:
                        self._tag_counter = int(idx)
                    except Exception:
                        pass
                except Exception:
                    pass
            if deleted_any:
                try:
                    event.accept()
                except Exception:
                    pass
                return
        super().keyPressEvent(event)



class MoveHandleItem(QGraphicsRectItem):
    def __init__(self, parent_text_item: 'ResizableTextItem'):
        super().__init__(parent_text_item)
        self.parent_text = parent_text_item
        size = 14
        self.setRect(-size / 2, -size / 2, size, size)
        self.setBrush(QColor(255, 85, 0))
        self.setPen(Qt.NoPen)
        self.setZValue(10)
        self.setCursor(Qt.SizeAllCursor)
        try:
            self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        except Exception:
            pass
        try:
            self.setAcceptedMouseButtons(Qt.LeftButton)
        except Exception:
            pass
        try:
            self.setAcceptHoverEvents(True)
        except Exception:
            pass
        self._hover = False

    def mousePressEvent(self, event):
        self._press_scene = event.scenePos()
        try:
            self._start_parent_pos = self.parent_text.pos()
        except Exception:
            self._start_parent_pos = QPointF(0, 0)
        try:
            self.parent_text.setSelected(True)
        except Exception:
            pass
        try:
            event.accept()
        except Exception:
            pass
        return

    def mouseMoveEvent(self, event):
        delta = event.scenePos() - self._press_scene
        try:
            new_pos = self._start_parent_pos + delta
            self.parent_text.setPos(new_pos)
            self.parent_text.update_move_handle_position()
        except Exception:
            pass
        try:
            event.accept()
        except Exception:
            pass
        return

    def mouseReleaseEvent(self, event):
        try:
            event.accept()
        except Exception:
            pass
        return


class TagItem(QGraphicsItem):
    def __init__(self, number: int, color: QColor):
        super().__init__()
        self.number = int(number)
        self.color = QColor(color)
        self.size = 28.0
        try:
            self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
        except Exception:
            pass
        try:
            self.setAcceptHoverEvents(True)
        except Exception:
            pass
        try:
            self.setZValue(9)
        except Exception:
            pass

    def boundingRect(self):
        s = float(self.size)
        return QRectF(-s / 2.0, -s / 2.0, s, s)

    def paint(self, painter, option, widget):
        try:
            painter.setRenderHint(QPainter.Antialiasing)
        except Exception:
            pass
        r = self.boundingRect()
        try:
            painter.setBrush(self.color)
        except Exception:
            pass
        try:
            painter.setPen(QPen(QColor(255, 255, 255), 2))
        except Exception:
            pass
        try:
            painter.drawEllipse(r)
        except Exception:
            pass
        txt = str(self.number)
        try:
            lum = (self.color.redF() * 0.299 + self.color.greenF() * 0.587 + self.color.blueF() * 0.114)
            tc = QColor(0, 0, 0) if lum > 0.7 else QColor(255, 255, 255)
            painter.setPen(QPen(tc))
        except Exception:
            pass
        try:
            fs = 14.0
            if len(txt) >= 2:
                fs = 12.0
            if len(txt) >= 3:
                fs = 10.0
            f = QFont()
            f.setPointSizeF(fs)
            f.setBold(True)
            painter.setFont(f)
            painter.drawText(r, Qt.AlignCenter, txt)
        except Exception:
            pass


class ResizableTextItem(QGraphicsTextItem):
    def __init__(self, text: str, color: QColor):
        super().__init__(text)
        self.setDefaultTextColor(color)
        # 默认非编辑态，避免单击进入编辑影响单击缩放体验
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        try:
            self.setFlags(
                QGraphicsItem.ItemIsSelectable
                | QGraphicsItem.ItemIsMovable
                | QGraphicsItem.ItemSendsGeometryChanges
            )
        except Exception:
            pass
        self.setAcceptHoverEvents(True)
        # 初始宽度为当前包围框宽度，便于后续可视化调整
        try:
            w = self.boundingRect().width()
        except Exception:
            w = 80.0
        if w <= 0:
            w = 80.0
        self.setTextWidth(float(w))
        self._move_handle = MoveHandleItem(self)
        self._move_handle.setVisible(False)
        self.update_move_handle_position()
        # 边缘命中与拖动状态
        self._hover_edge = None  # 'left' or 'right'
        self._resize_active = False
        self._resize_edge = None
        self._press_scene = QPointF(0, 0)
        self._start_width = float(w)
        self._start_pos = QPointF(0, 0)
        # 文本内容变化时，更新手柄位置
        try:
            self.document().contentsChanged.connect(self.update_move_handle_position)
        except Exception:
            pass

    def update_move_handle_position(self):
        try:
            rect = self.boundingRect()
            btn_h = float(self._move_handle.rect().height())
            top_center = QPointF(rect.center().x(), rect.top() - btn_h / 2.0 - 2.0)
            self._move_handle.setPos(top_center)
        except Exception:
            pass

    def itemChange(self, change, value):
        try:
            # 选中状态变化时显示/隐藏移动手柄
            if change in (
                QGraphicsItem.GraphicsItemChange.ItemSelectedChange,
                QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged,
            ):
                try:
                    vis = bool(value)
                except Exception:
                    vis = self.isSelected()
                self._move_handle.setVisible(vis)
        except Exception:
            pass
        try:
            # 位置变化时更新移动手柄位置
            if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
                self.update_move_handle_position()
        except Exception:
            pass
        return super().itemChange(change, value)

    # 绘制选中边框，便于可视化拖动
    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        try:
            if self.isSelected() or self._hover_edge is not None or self._resize_active:
                from PySide6.QtGui import QPen
                pen = QPen(QColor(255, 140, 0), 1, Qt.DashLine)
                painter.setPen(pen)
                painter.drawRect(self.boundingRect())
        except Exception:
            pass

    def hoverMoveEvent(self, event):
        try:
            local = self.mapFromScene(event.scenePos())
            rect = self.boundingRect()
            m = 6.0
            edge = None
            if abs(local.x() - rect.left()) <= m:
                edge = 'left'
            elif abs(local.x() - rect.right()) <= m:
                edge = 'right'
            self._hover_edge = edge
            if edge in ('left', 'right'):
                self.setCursor(Qt.SizeHorCursor)
            else:
                self.unsetCursor()
            event.accept()
        except Exception:
            pass
        return super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        try:
            self._hover_edge = None
            self.unsetCursor()
        except Exception:
            pass
        return super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        # 编辑态：遵循默认行为；非编辑态：左/右边框拖动调整文本宽度
        try:
            if bool(self.textInteractionFlags() & Qt.TextEditorInteraction):
                return super().mousePressEvent(event)
        except Exception:
            pass
        if event.button() == Qt.LeftButton and self._hover_edge in ('left', 'right'):
            self._resize_active = True
            self._resize_edge = self._hover_edge
            self._press_scene = event.scenePos()
            tw = float(self.textWidth()) if self.textWidth() > 0 else float(self.boundingRect().width())
            self._start_width = tw
            self._start_pos = self.pos()
            try:
                event.accept()
            except Exception:
                pass
            return
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resize_active:
            try:
                dx = event.scenePos().x() - self._press_scene.x()
                min_w, max_w = 40.0, 1600.0
                if self._resize_edge == 'right':
                    new_w = max(min_w, min(max_w, self._start_width + dx))
                    self.setTextWidth(float(new_w))
                else:  # left edge
                    new_w = max(min_w, min(max_w, self._start_width - dx))
                    self.setTextWidth(float(new_w))
                    shift = self._start_width - new_w
                    self.setPos(QPointF(self._start_pos.x() + shift, self._start_pos.y()))
                self.update_move_handle_position()
                try:
                    event.accept()
                except Exception:
                    pass
                return
            except Exception:
                pass
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resize_active:
            self._resize_active = False
            self._resize_edge = None
            try:
                event.accept()
            except Exception:
                pass
            return
        return super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        # 双击进入编辑模式
        try:
            self.setTextInteractionFlags(Qt.TextEditorInteraction)
            self.setFocus(Qt.MouseFocusReason)
        except Exception:
            pass
        return super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        # 失焦退出编辑模式
        try:
            self.setTextInteractionFlags(Qt.NoTextInteraction)
        except Exception:
            pass
        return super().focusOutEvent(event)


class EditorWindow(QMainWindow):
    def __init__(self, base_pixmap: QPixmap):
        super().__init__()
        self.setWindowTitle("FastCap 编辑器")
        self.setWindowIcon(create_app_icon())
        self.pin_windows = []  # 保持贴图窗口引用，避免被回收

        self.scene = QGraphicsScene(self)
        self.view = EditorView(self.scene, ToolState())
        self.setCentralWidget(self.view)

        self.base_item = QGraphicsPixmapItem(base_pixmap)
        # 禁用平滑变换，保持像素清晰
        try:
            self.base_item.setTransformationMode(Qt.FastTransformation)
        except Exception:
            pass
        self.scene.addItem(self.base_item)
        self.scene.setSceneRect(QRectF(QPoint(0, 0), base_pixmap.size()))

        self._build_toolbar()
        # 快捷键：Ctrl+W 关闭窗口
        try:
            self._sc_close = QShortcut(QKeySequence("Ctrl+W"), self)
            self._sc_close.activated.connect(self.close)
        except Exception:
            pass
        # 其他快捷键：工具与常用动作
        try:
            self._sc_tool_rect = QShortcut(QKeySequence("R"), self)
            self._sc_tool_rect.activated.connect(lambda: self._set_tool("rect"))

            self._sc_tool_arrow = QShortcut(QKeySequence("A"), self)
            self._sc_tool_arrow.activated.connect(lambda: self._set_tool("arrow"))

            self._sc_tool_text = QShortcut(QKeySequence("T"), self)
            self._sc_tool_text.activated.connect(lambda: self._set_tool("text"))

            self._sc_tool_brush = QShortcut(QKeySequence("B"), self)
            self._sc_tool_brush.activated.connect(lambda: self._set_tool("brush"))

            self._sc_copy = QShortcut(QKeySequence("Ctrl+C"), self)
            self._sc_copy.activated.connect(self.copy_to_clipboard)

            self._sc_save = QShortcut(QKeySequence("Ctrl+S"), self)
            self._sc_save.activated.connect(self.save_to_file)

            self._sc_esc = QShortcut(QKeySequence("Esc"), self)
            self._sc_esc.activated.connect(self.close)
        except Exception:
            pass
        self.resize(min(1200, base_pixmap.width() + 80), min(800, base_pixmap.height() + 120))

    def _build_toolbar(self):
        tb = QToolBar("工具", self)
        self.addToolBar(tb)
        try:
            tb.setStyleSheet("QToolBar::separator { width: 1px; margin-left: 4px; margin-right: 4px; } QToolButton { margin-left: 0px; margin-right: 0px; } QLabel { margin-left: 0px; margin-right: 0px; } QComboBox { margin-left: 0px; margin-right: 0px; }")
        except Exception:
            pass

        act_reset_mouse = QAction("恢复鼠标默认", self)
        act_reset_mouse.triggered.connect(lambda: self._set_tool("none"))
        tb.addAction(act_reset_mouse)

        act_rect = QAction("矩形", self)
        act_rect.triggered.connect(lambda: self._set_tool("rect"))
        tb.addAction(act_rect)

        act_arrow = QAction("箭头", self)
        act_arrow.triggered.connect(lambda: self._set_tool("arrow"))
        tb.addAction(act_arrow)

        act_brush = QAction("画笔", self)
        act_brush.triggered.connect(lambda: self._set_tool("brush"))
        tb.addAction(act_brush)

        act_tag = QAction("标签", self)
        act_tag.triggered.connect(lambda: self._set_tool("tag"))
        tb.addAction(act_tag)

        tb.addSeparator()

        tb.addWidget(QLabel("颜色:"))
        self.color_combo = QComboBox(self)
        self.color_combo.addItems(["红", "绿", "蓝", "黄", "白", "黑"])
        color_map = {
            "红": QColor(255, 0, 0),
            "绿": QColor(0, 180, 0),
            "蓝": QColor(40, 120, 255),
            "黄": QColor(255, 200, 0),
            "白": QColor(255, 255, 255),
            "黑": QColor(0, 0, 0),
        }
        default_index = 0
        current = self.view.tool_state.color
        try:
            for i, name in enumerate(["红", "绿", "蓝", "黄", "白", "黑"]):
                if current == color_map[name]:
                    default_index = i
                    break
        except Exception:
            pass
        self.color_combo.setCurrentIndex(default_index)
        self.color_combo.currentTextChanged.connect(lambda text: self._set_color(color_map.get(text, QColor(255, 0, 0))))
        try:
            self.color_combo.setMinimumWidth(60)
        except Exception:
            pass
        tb.addWidget(self.color_combo)

        tb.addWidget(QLabel("线宽:"))
        self.width_combo = QComboBox(self)
        self.width_combo.addItems(["1px", "2px", "3px", "5px", "8px", "12px"])
        try:
            current_w = int(self.view.tool_state.width)
        except Exception:
            current_w = 3
        preset = [1, 2, 3, 5, 8, 12]
        if current_w in preset:
            self.width_combo.setCurrentIndex(preset.index(current_w))
        else:
            self.width_combo.setCurrentIndex(2)
        self.width_combo.currentTextChanged.connect(
            lambda text: self._set_width(int(text.replace("px", "")))
        )
        try:
            self.width_combo.setMinimumWidth(60)
        except Exception:
            pass
        tb.addWidget(self.width_combo)

        tb.addSeparator()

        act_text = QAction("文字", self)
        act_text.triggered.connect(lambda: self._set_tool("text"))
        tb.addAction(act_text)

        tb.addWidget(QLabel("文字大小:"))
        self.font_combo = QComboBox(self)
        self.font_combo.addItems(["10", "12", "14", "16", "18", "22", "26", "32"])
        try:
            fs = int(self.view.tool_state.font_size)
        except Exception:
            fs = 14
        preset = [10, 12, 14, 16, 18, 22, 26, 32]
        if fs in preset:
            self.font_combo.setCurrentIndex(preset.index(fs))
        else:
            self.font_combo.setCurrentIndex(2)
        self.font_combo.currentTextChanged.connect(self._set_font_size)
        try:
            self.font_combo.setMinimumWidth(60)
        except Exception:
            pass
        tb.addWidget(self.font_combo)

        tb.addSeparator()

        act_undo = QAction("撤销", self)
        act_undo.setShortcut("Ctrl+Z")
        act_undo.triggered.connect(self.view.undo)
        tb.addAction(act_undo)

        act_copy = QAction("复制", self)
        act_copy.triggered.connect(self.copy_to_clipboard)
        tb.addAction(act_copy)

        act_save = QAction("保存", self)
        act_save.triggered.connect(self.save_to_file)
        tb.addAction(act_save)

        act_close = QAction("关闭", self)
        act_close.triggered.connect(self.close)
        tb.addAction(act_close)

    def _set_tool(self, tool: str):
        self.view.tool_state.tool = tool

    def _set_color(self, color: QColor):
        self.view.tool_state.color = color
        try:
            for it in self.scene.selectedItems():
                from PySide6.QtWidgets import QGraphicsTextItem as _QtTextItem
                if isinstance(it, (ResizableTextItem, _QtTextItem)):
                    try:
                        it.setDefaultTextColor(color)
                    except Exception:
                        pass
        except Exception:
            pass

    def _set_width(self, width: int):
        self.view.tool_state.width = width

    def _set_font_size(self, text: str):
        try:
            fs = float(text)
        except Exception:
            fs = float(self.view.tool_state.font_size)
        self.view.tool_state.font_size = fs
        try:
            for it in self.scene.selectedItems():
                from PySide6.QtWidgets import QGraphicsTextItem as _QtTextItem
                if isinstance(it, (ResizableTextItem, _QtTextItem)):
                    f = it.font()
                    try:
                        f.setPointSizeF(fs)
                    except Exception:
                        pass
                    it.setFont(f)
                    try:
                        if hasattr(it, "update_move_handle_position"):
                            it.update_move_handle_position()
                    except Exception:
                        pass
        except Exception:
            pass

    def _render_image(self, for_clipboard: bool = False) -> QImage:
        try:
            dpr = float(self.base_item.pixmap().devicePixelRatio())
        except Exception:
            dpr = 1.0
        if dpr < 1.0:
            dpr = 1.0
        if for_clipboard:
            br = self.scene.itemsBoundingRect()
            try:
                m = 3.0
                br.adjust(-m, -m, m, m)
            except Exception:
                pass
            scale = dpr
            img = QImage(int(br.width() * scale), int(br.height() * scale), QImage.Format_ARGB32)
            try:
                img.setDevicePixelRatio(1.0)
            except Exception:
                pass
            img.fill(Qt.transparent)
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setRenderHint(QPainter.TextAntialiasing, True)
            p.setRenderHint(QPainter.SmoothPixmapTransform, False)
            p.scale(scale, scale)
            self.scene.render(p, QRectF(0, 0, br.width(), br.height()), br)
            p.end()
            return img
        else:
            br = self.scene.itemsBoundingRect()
            try:
                m = 8.0
                br.adjust(-m, -m, m, m)
            except Exception:
                pass
            scale = dpr
            img = QImage(int(br.width() * scale), int(br.height() * scale), QImage.Format_ARGB32)
            try:
                img.setDevicePixelRatio(dpr)
            except Exception:
                pass
            img.fill(Qt.transparent)
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setRenderHint(QPainter.TextAntialiasing, True)
            p.setRenderHint(QPainter.SmoothPixmapTransform, False)
            p.scale(scale, scale)
            self.scene.render(p, QRectF(0, 0, br.width(), br.height()), br)
            p.end()
            return img

    def copy_to_clipboard(self):
        img = self._render_image(True)
        pix = QPixmap.fromImage(img)
        try:
            pix.setDevicePixelRatio(1.0)
        except Exception:
            pass
        QGuiApplication.clipboard().setPixmap(pix)

    def save_to_file(self):
        ts = time.strftime("%Y%m%d_%H%M%S")
        path, _ = QFileDialog.getSaveFileName(self, "保存图像", f"screenshot_{ts}.png", "PNG (*.png)")
        if not path:
            return
        # 与复制逻辑一致：使用 itemsBoundingRect 内容区域、以场景 DPR 渲染，避免裁剪缺失或空白，保持清晰度与大小
        img = self._render_image(True)
        if not img.save(path, "PNG"):
            QMessageBox.warning(self, "保存失败", "无法保存到该路径")



class PinWindow(QMainWindow):
    def __init__(self, pix: QPixmap):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.label_pix = QGraphicsPixmapItem(pix)
        self.scene = QGraphicsScene(self)
        self.scene.addItem(self.label_pix)
        self.view = QGraphicsView(self.scene)
        self.setCentralWidget(self.view)
        self.resize(pix.width() + 8, pix.height() + 8)
        self._dragging = False
        self._drag_start = QPoint()

        tb = QToolBar("贴图", self)
        self.addToolBar(tb)
        act_copy = QAction("复制", self)
        act_copy.triggered.connect(lambda: QGuiApplication.clipboard().setPixmap(pix))
        tb.addAction(act_copy)
        act_close = QAction("关闭", self)
        act_close.triggered.connect(self.close)
        tb.addAction(act_close)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_start)

    def mouseReleaseEvent(self, event):
        self._dragging = False

class ScrollWorker(QThread):
    """浏览器模式滚动截图 - 使用现有方案"""
    finished = Signal(list)

    def __init__(self, rect: QRect, parent=None):
        super().__init__(parent)
        self.rect = rect
        self._running = True
        self.scroll_step = 200
        self.pause_sec = 0.12
        self.max_steps = 60
        self.stable_limit = 2

    def run(self):
        frames = []
        _cursor_hide()
        try:
            first = capture_region(self.rect)
            frames.append(first)
            cx = self.rect.left() + 6
            cy = self.rect.top() + 6
            try:
                pyautogui.FAILSAFE = False
            except Exception:
                pass
            last_np = qpixmap_to_np_rgb(first)
            stable_count = 0
            fallback_used = False
            wheel_sign = -1
            ideal_off = 0
            skips_next = 0
            hist_dist = []
            for i in range(self.max_steps):
                if not self._running:
                    break
                try:
                    reps = max(1, int(1 + skips_next))
                    delta = int(round(wheel_sign * self.scroll_step / 120.0)) * 120
                    for _ in range(reps):
                        _wheel_scroll(delta)
                        time.sleep(max(0.04, self.pause_sec / 2))
                except Exception:
                    pass
                time.sleep(self.pause_sec)
                cur = capture_region(self.rect)
                cur_np = qpixmap_to_np_rgb(cur)
                diff = np.mean(np.abs(np.mean(cur_np, axis=2) - np.mean(last_np, axis=2)))
                try:
                    h = min(last_np.shape[0], cur_np.shape[0])
                    ig = max(0, int(h * 0.08))
                    k = max(1, int(h * 0.06))
                    ts = ig
                    te = min(h, ig + k)
                    be = max(0, h - ig)
                    bs = max(0, be - k)
                    last_top = last_np[ts:te, :, :]
                    cur_top = cur_np[ts:te, :, :]
                    last_bottom = last_np[bs:be, :, :]
                    cur_bottom = cur_np[bs:be, :, :]
                    same_top = bool(last_top.shape == cur_top.shape and np.array_equal(last_top, cur_top))
                    same_bottom = bool(last_bottom.shape == cur_bottom.shape and np.array_equal(last_bottom, cur_bottom))
                    stop_overlap = same_top and same_bottom
                except Exception:
                    stop_overlap = False
                off_est = 0
                err_est = 1e9
                try:
                    cb = _col_sampling(last_np)
                    cc = _col_sampling(cur_np)
                    pred = h // 2 if ideal_off <= 0 else int(ideal_off)
                    off_est, err_est = _diff_overlap(cb, cc, predict=pred, approx_diff=0.18, min_overlap=max(60, int(h * 0.2)))
                except Exception:
                    off_est = 0
                near_full_overlap = (h > 0) and (off_est >= max(1, h - 8))
                frames.append(cur)
                if stop_overlap or near_full_overlap:
                    stable_count += 1
                else:
                    stable_count = 0
                try:
                    dist_px = max(1, h - int(off_est))
                    hist_dist.append(dist_px)
                    if len(hist_dist) > 8:
                        hist_dist = hist_dist[-8:]
                    avg_dist = sum(hist_dist) / max(1, len(hist_dist))
                    skips_next = max(0, min(3, int(self.scroll_step / max(1, avg_dist)) - 1))
                    ideal_off = int(off_est) if ideal_off <= 0 else int(0.7 * ideal_off + 0.3 * off_est)
                except Exception:
                    skips_next = 0
                last_np = cur_np
                if stable_count >= self.stable_limit:
                    break
            
        finally:
            _cursor_show()
            self.finished.emit(frames)

    def stop(self):
        self._running = False


class NativeScrollWorker(QThread):
    """非浏览器模式滚动截图 - 改进的方案，适用于原生应用"""
    finished = Signal(list)
    progress = Signal(int, int)  # current, total

    def __init__(self, rect: QRect, parent=None):
        super().__init__(parent)
        self.rect = rect
        self._running = True
        # 非浏览器模式使用更小的滚动步长和更长的等待时间
        self.scroll_step = 120  # 更小的步长，更精确
        self.pause_sec = 0.25  # 更长的等待时间，确保渲染完成
        self.max_steps = 100
        self.stable_limit = 3  # 需要更多次确认才停止

    def run(self):
        frames = []
        _cursor_hide()
        try:
            # 将鼠标移到选区中心，确保焦点在正确的窗口
            center_x = self.rect.left() + self.rect.width() // 2
            center_y = self.rect.top() + self.rect.height() // 2
            try:
                pyautogui.FAILSAFE = False
                pyautogui.moveTo(center_x, center_y)
                time.sleep(0.1)
                # 点击一次确保窗口获得焦点
                pyautogui.click()
                time.sleep(0.2)
            except Exception:
                pass

            # 捕获第一帧
            first = capture_region(self.rect)
            frames.append(first)
            last_np = qpixmap_to_np_rgb(first)
            
            stable_count = 0
            no_change_count = 0
            
            for i in range(self.max_steps):
                if not self._running:
                    break
                
                self.progress.emit(i + 1, self.max_steps)
                
                # 执行滚动
                try:
                    # 使用Page Down键进行滚动，对非浏览器应用更可靠
                    pyautogui.press('pagedown')
                except Exception:
                    # 如果Page Down失败，回退到鼠标滚轮
                    try:
                        delta = -self.scroll_step
                        _wheel_scroll(delta)
                    except Exception:
                        pass
                
                # 等待渲染完成
                time.sleep(self.pause_sec)
                
                # 捕获当前帧
                cur = capture_region(self.rect)
                cur_np = qpixmap_to_np_rgb(cur)
                
                # 检测是否有变化
                diff = np.mean(np.abs(cur_np.astype(np.float32) - last_np.astype(np.float32)))
                
                # 如果变化很小，可能已经到底部
                if diff < 1.0:
                    no_change_count += 1
                    if no_change_count >= 3:
                        # 连续3次没有变化，停止（不添加当前帧）
                        break
                else:
                    no_change_count = 0
                
                # 检测是否到达底部（顶部和底部都相同）
                is_at_bottom = False
                try:
                    h = min(last_np.shape[0], cur_np.shape[0])
                    # 检查顶部区域
                    top_h = max(10, int(h * 0.1))
                    last_top = last_np[:top_h, :, :]
                    cur_top = cur_np[:top_h, :, :]
                    # 检查底部区域
                    bottom_h = max(10, int(h * 0.1))
                    last_bottom = last_np[-bottom_h:, :, :]
                    cur_bottom = cur_np[-bottom_h:, :, :]
                    
                    top_same = np.array_equal(last_top, cur_top)
                    bottom_same = np.array_equal(last_bottom, cur_bottom)
                    
                    if top_same and bottom_same:
                        stable_count += 1
                        is_at_bottom = True
                    else:
                        stable_count = 0
                    
                    if stable_count >= self.stable_limit:
                        # 到达底部，停止（不添加当前帧）
                        break
                except Exception:
                    pass
                
                # 只有在内容有实质性变化时才添加帧
                # 避免添加重复的帧
                if not is_at_bottom and diff >= 1.0:
                    frames.append(cur)
                    last_np = cur_np
                elif diff >= 5.0:
                    # 如果差异较大，即使检测到可能在底部也添加
                    frames.append(cur)
                    last_np = cur_np
            
        finally:
            _cursor_show()
            self.finished.emit(frames)

    def stop(self):
        self._running = False


class RecorderWindow(QMainWindow):
    def __init__(self, rect: QRect):
        super().__init__()
        self.setWindowTitle("屏幕录像")
        self.rect = rect
        self.fps = 15
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._capture_frame)
        self.frames = []
        self.start_time = None
        self.statusBar().showMessage("就绪")
        tb = QToolBar("录像", self)
        self.addToolBar(tb)
        act_start = QAction("开始", self)
        act_start.triggered.connect(self.start_record)
        tb.addAction(act_start)
        act_stop = QAction("停止并保存", self)
        act_stop.triggered.connect(self.stop_record)
        tb.addAction(act_stop)

        self.audio_recorder = None
        self.audio_mode = "both"
        self.audio_enabled = True
        self.mic_gain = 1.0
        self.sys_gain = 1.0
        from PySide6.QtWidgets import QLabel, QComboBox
        tb.addSeparator()
        tb.addWidget(QLabel("音频源:"))
        self.audio_combo = QComboBox(self)
        self.audio_combo.addItems(["两者", "麦克风", "系统", "无"]) 
        self.audio_combo.setCurrentIndex(0)
        self.audio_combo.currentTextChanged.connect(self._set_audio_mode)
        try:
            self.audio_combo.setMinimumWidth(96)
        except Exception:
            pass
        tb.addWidget(self.audio_combo)

        tb.addSeparator()
        tb.addWidget(QLabel("麦克风增益:"))
        self.mic_gain_combo = QComboBox(self)
        self.mic_gain_combo.addItems(["0.5x", "0.8x", "1.0x", "1.2x", "1.5x", "2.0x"])
        self.mic_gain_combo.setCurrentText("1.0x")
        self.mic_gain_combo.currentTextChanged.connect(self._set_mic_gain)
        try:
            self.mic_gain_combo.setMinimumWidth(96)
        except Exception:
            pass
        tb.addWidget(self.mic_gain_combo)

        tb.addWidget(QLabel("系统增益:"))
        self.sys_gain_combo = QComboBox(self)
        self.sys_gain_combo.addItems(["0.5x", "0.8x", "1.0x", "1.2x", "1.5x", "2.0x"])
        self.sys_gain_combo.setCurrentText("1.0x")
        self.sys_gain_combo.currentTextChanged.connect(self._set_sys_gain)
        try:
            self.sys_gain_combo.setMinimumWidth(96)
        except Exception:
            pass
        tb.addWidget(self.sys_gain_combo)

    def _bbox(self):
        return {
            "left": self.rect.left(),
            "top": self.rect.top(),
            "width": self.rect.width(),
            "height": self.rect.height(),
        }

    def start_record(self):
        if self.timer.isActive():
            return
        self.frames = []
        self.start_time = time.time()
        self.timer.start(int(1000 / self.fps))
        self.statusBar().showMessage("录制中…")
        self._update_title()
        try:
            p = capture_region(self.rect)
            self._frame_w = p.width()
            self._frame_h = p.height()
        except Exception:
            self._frame_w = self.rect.width()
            self._frame_h = self.rect.height()
        if self.audio_enabled:
            try:
                self.audio_recorder = AudioRecorder(source=self.audio_mode)
                self.audio_recorder.start()
            except Exception as e:
                QMessageBox.warning(self, "音频录制失败", f"无法启动音频录制: {e}")
                self.audio_enabled = False

    def _capture_frame(self):
        try:
            pix = capture_region(self.rect)
            arr = qpixmap_to_np_rgb(pix)
            self.frames.append(arr)
        except Exception as e:
            self.statusBar().showMessage(f"采集失败：{e}")
        self._update_title()

    def _update_title(self):
        if self.start_time:
            dur = time.time() - self.start_time
            self.setWindowTitle(f"屏幕录像 - 录制中（{len(self.frames)}帧，{dur:.1f}s）")
        else:
            self.setWindowTitle("屏幕录像")

    def stop_record(self):
        if self.timer.isActive():
            self.timer.stop()
        if not self.frames:
            QMessageBox.information(self, "提示", "没有录到任何帧")
            return
        ts = time.strftime("%Y%m%d_%H%M%S")
        path, _ = QFileDialog.getSaveFileName(self, "保存视频", f"record_{ts}.mp4", "MP4 (*.mp4)")
        if not path:
            return

        # 临时视频文件（仅视频流）
        tmp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        tmp_video_path = tmp_video.name
        tmp_video.close()
        save_ok = False
        try:
            import imageio
            try:
                writer = imageio.get_writer(tmp_video_path, fps=self.fps, codec='libx264')
            except Exception:
                writer = imageio.get_writer(tmp_video_path, fps=self.fps, codec='mpeg4')
            fw = int(getattr(self, '_frame_w', self.rect.width()))
            fh = int(getattr(self, '_frame_h', self.rect.height()))
            for f in self.frames:
                try:
                    if f.shape[1] != fw or f.shape[0] != fh:
                        f = f[:fh, :fw, :]
                except Exception:
                    pass
                writer.append_data(f)
            writer.close()
            save_ok = True
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"写入视频失败：{e}\n临时文件: {tmp_video_path}")

        audio_combined = False
        if save_ok and self.audio_enabled and self.audio_recorder:
            try:
                audio_data, samplerate, channels = self.audio_recorder.stop()
            except Exception as e:
                audio_data = None
                QMessageBox.warning(self, "音频提示", f"停止音频录制失败，将保存纯视频：{e}")
            try:
                from imageio_ffmpeg import get_ffmpeg_exe
                ffmpeg = get_ffmpeg_exe()
            except Exception:
                ffmpeg = os.environ.get("IMAGEIO_FFMPEG_EXE")
            try:
                if self.audio_mode == "both" and hasattr(self.audio_recorder, "tracks"):
                    mic, sysa = self.audio_recorder.tracks()
                    tmp_mic = tmp_sys = None
                    if mic is not None and mic.size > 0:
                        t1 = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                        tmp_mic = t1.name
                        t1.close()
                        write_wav(tmp_mic, mic, samplerate, 1)
                    if sysa is not None and sysa.size > 0:
                        t2 = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                        tmp_sys = t2.name
                        t2.close()
                        write_wav(tmp_sys, sysa, samplerate, 1)
                    if ffmpeg and tmp_mic and tmp_sys:
                        try:
                            flt = f"[1:a]volume={self.mic_gain:.3f}[a1];[2:a]volume={self.sys_gain:.3f}[a2];[a1][a2]amix=inputs=2:duration=shortest:normalize=1"
                            cmd = [
                                ffmpeg, "-y",
                                "-i", tmp_video_path,
                                "-i", tmp_mic,
                                "-i", tmp_sys,
                                "-filter_complex", flt,
                                "-c:v", "copy",
                                "-c:a", "aac",
                                "-shortest",
                                path,
                            ]
                            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            audio_combined = True
                            os.unlink(tmp_video_path)
                            os.unlink(tmp_mic)
                            os.unlink(tmp_sys)
                        except Exception:
                            audio_combined = False
                    elif ffmpeg and (tmp_mic or tmp_sys):
                        one = tmp_mic or tmp_sys
                        try:
                            g = self.mic_gain if tmp_mic else self.sys_gain
                            cmd = [
                                ffmpeg, "-y",
                                "-i", tmp_video_path,
                                "-i", one,
                                "-filter:a", f"volume={g:.3f}",
                                "-c:v", "copy",
                                "-c:a", "aac",
                                "-shortest",
                                path,
                            ]
                            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            audio_combined = True
                            os.unlink(tmp_video_path)
                            os.unlink(one)
                        except Exception:
                            audio_combined = False
                elif audio_data is not None and audio_data.size > 0 and ffmpeg:
                    tmp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                    tmp_audio_path = tmp_audio.name
                    tmp_audio.close()
                    write_wav(tmp_audio_path, audio_data, samplerate, channels)
                    try:
                        g = self.mic_gain if self.audio_mode == "mic" else (self.sys_gain if self.audio_mode == "system" else 1.0)
                        cmd = [
                            ffmpeg, "-y",
                            "-i", tmp_video_path,
                            "-i", tmp_audio_path,
                            "-filter:a", f"volume={g:.3f}",
                            "-c:v", "copy",
                            "-c:a", "aac",
                            "-shortest",
                            path,
                        ]
                        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        audio_combined = True
                        os.unlink(tmp_video_path)
                        os.unlink(tmp_audio_path)
                    except Exception:
                        audio_combined = False
            except Exception:
                audio_combined = False

        if save_ok and not audio_combined:
            try:
                if os.path.exists(path):
                    os.unlink(path)
                os.replace(tmp_video_path, path)
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"移动文件失败：{e}")
                QMessageBox.information(self, "临时保留", f"视频临时文件保留在：{tmp_video_path}")
                return

        if save_ok:
            QMessageBox.information(self, "完成", "视频已保存")
            self.statusBar().showMessage("已保存")

        # 重置状态
        self.frames = []
        self.start_time = None
        self._update_title()

    def _set_audio_mode(self, text: str):
        m = {
            "两者": "both",
            "麦克风": "mic",
            "系统": "system",
            "无": "none",
        }.get(text, "both")
        self.audio_mode = m
        self.audio_enabled = m != "none"
        msg = {
            "both": "录制麦克风和系统音频",
            "mic": "仅录制麦克风音频",
            "system": "仅录制系统音频",
            "none": "不录制音频",
        }[m]
        self.statusBar().showMessage(msg, 3000)

    def _set_mic_gain(self, text: str):
        try:
            self.mic_gain = float(text.replace("x", ""))
        except Exception:
            self.mic_gain = 1.0

    def _set_sys_gain(self, text: str):
        try:
            self.sys_gain = float(text.replace("x", ""))
        except Exception:
            self.sys_gain = 1.0


class AudioRecorder:
    def __init__(self, samplerate: int = 48000, channels: int = 1, source: str = "both"):
        self.samplerate = samplerate
        self.channels = channels
        self.source = source
        self._running = False
        self._buf_mic = []
        self._buf_sys = []
        self._mic_stream = None
        self._sys_stream = None

    def _mic_cb(self, indata, frames, time_info, status):
        if self._running:
            try:
                self._buf_mic.append(indata.copy())
            except Exception:
                pass

    def _sys_cb(self, indata, frames, time_info, status):
        if self._running:
            try:
                self._buf_sys.append(indata.copy())
            except Exception:
                pass

    def start(self):
        self._buf_mic.clear()
        self._buf_sys.clear()
        if sd is None:
            self._running = False
            self._mic_stream = None
            self._sys_stream = None
            return
        self._running = True
        if self.source in ("mic", "both"):
            try:
                self._mic_stream = sd.InputStream(
                    samplerate=self.samplerate,
                    channels=1,
                    dtype="float32",
                    callback=self._mic_cb,
                )
                self._mic_stream.start()
            except Exception:
                self._mic_stream = None
        if self.source in ("system", "both"):
            try:
                dev_out = None
                try:
                    d = sd.default.device
                    if isinstance(d, (list, tuple)) and len(d) >= 2:
                        dev_out = d[1]
                except Exception:
                    dev_out = None
                extra = None
                try:
                    extra = getattr(sd, "WasapiSettings")(loopback=True)
                except Exception:
                    extra = None
                kwargs = {
                    "samplerate": self.samplerate,
                    "channels": 2,
                    "dtype": "float32",
                    "callback": self._sys_cb,
                }
                if dev_out is not None:
                    kwargs["device"] = dev_out
                if extra is not None:
                    kwargs["extra_settings"] = extra
                self._sys_stream = sd.InputStream(**kwargs)
                self._sys_stream.start()
            except Exception:
                try:
                    self._sys_stream = sd.InputStream(
                        samplerate=self.samplerate,
                        channels=2,
                        dtype="float32",
                        callback=self._sys_cb,
                    )
                    self._sys_stream.start()
                except Exception:
                    self._sys_stream = None

    def stop(self):
        self._running = False
        try:
            if self._mic_stream:
                self._mic_stream.stop()
                self._mic_stream.close()
        except Exception:
            pass
        try:
            if self._sys_stream:
                self._sys_stream.stop()
                self._sys_stream.close()
        except Exception:
            pass
        self._mic_stream = None
        self._sys_stream = None
        import numpy as np
        mic = None
        sysa = None
        try:
            if self._buf_mic:
                mic = np.concatenate(self._buf_mic, axis=0)
                if mic.ndim == 2 and mic.shape[1] > 1:
                    mic = mic.mean(axis=1, keepdims=True)
        except Exception:
            mic = None
        try:
            if self._buf_sys:
                sysa = np.concatenate(self._buf_sys, axis=0)
                if sysa.ndim == 2 and sysa.shape[1] > 1:
                    sysa = sysa.mean(axis=1, keepdims=True)
        except Exception:
            sysa = None
        if self.source == "mic":
            if mic is None:
                return None, self.samplerate, 1
            return mic, self.samplerate, 1
        if self.source == "system":
            if sysa is None:
                return None, self.samplerate, 1
            return sysa, self.samplerate, 1
        if mic is None and sysa is None:
            return None, self.samplerate, 1
        if mic is None:
            return sysa, self.samplerate, 1
        if sysa is None:
            return mic, self.samplerate, 1
        n = min(mic.shape[0], sysa.shape[0])
        mix = (mic[:n] + sysa[:n]) * 0.5
        return mix, self.samplerate, 1

    def tracks(self):
        import numpy as np
        m = None
        s = None
        try:
            if self._buf_mic:
                m = np.concatenate(self._buf_mic, axis=0)
                if m.ndim == 2 and m.shape[1] > 1:
                    m = m.mean(axis=1, keepdims=True)
        except Exception:
            m = None
        try:
            if self._buf_sys:
                s = np.concatenate(self._buf_sys, axis=0)
                if s.ndim == 2 and s.shape[1] > 1:
                    s = s.mean(axis=1, keepdims=True)
        except Exception:
            s = None
        return m, s


def write_wav(path: str, data: np.ndarray, samplerate: int, channels: int):
    # float32 [-1,1] -> int16 PCM
    pcm = np.clip(data, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(pcm.tobytes())

    def _capture_frame(self):
        with mss.mss() as sct:
            try:
                shot = sct.grab(self._bbox())
                frame = np.array(shot)[:, :, :3][:, :, ::-1]
                self.frames.append(frame)
            except Exception as e:
                self.statusBar().showMessage(f"采集失败：{e}")
        self._update_title()

    def _update_title(self):
        if self.start_time:
            dur = time.time() - self.start_time
            self.setWindowTitle(f"屏幕录像 - 录制中（{len(self.frames)}帧，{dur:.1f}s）")
        else:
            self.setWindowTitle("屏幕录像")

    def stop_record(self):
        if self.timer.isActive():
            self.timer.stop()
        if not self.frames:
            QMessageBox.information(self, "提示", "没有录到任何帧")
            return
        ts = time.strftime("%Y%m%d_%H%M%S")
        path, _ = QFileDialog.getSaveFileName(self, "保存视频", f"record_{ts}.mp4", "MP4 (*.mp4)")
        if not path:
            return

        # 临时视频文件（仅视频流）
        tmp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        tmp_video_path = tmp_video.name
        tmp_video.close()
        save_ok = False
        try:
            import imageio
            try:
                writer = imageio.get_writer(tmp_video_path, fps=self.fps, codec='libx264')
            except Exception:
                writer = imageio.get_writer(tmp_video_path, fps=self.fps, codec='mpeg4')
            fw = int(getattr(self, '_frame_w', self.rect.width()))
            fh = int(getattr(self, '_frame_h', self.rect.height()))
            for f in self.frames:
                try:
                    if f.shape[1] != fw or f.shape[0] != fh:
                        f = f[:fh, :fw, :]
                except Exception:
                    pass
                writer.append_data(f)
            writer.close()
            save_ok = True
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"写入视频失败：{e}\n临时文件: {tmp_video_path}")

        audio_combined = False
        if save_ok and self.audio_enabled and self.audio_recorder:
            try:
                audio_data, samplerate, channels = self.audio_recorder.stop()
            except Exception as e:
                audio_data = None
                QMessageBox.warning(self, "音频提示", f"停止音频录制失败，将保存纯视频：{e}")
            try:
                from imageio_ffmpeg import get_ffmpeg_exe
                ffmpeg = get_ffmpeg_exe()
            except Exception:
                ffmpeg = os.environ.get("IMAGEIO_FFMPEG_EXE")
            try:
                if self.audio_mode == "both" and hasattr(self.audio_recorder, "tracks"):
                    mic, sysa = self.audio_recorder.tracks()
                    tmp_mic = tmp_sys = None
                    if mic is not None and mic.size > 0:
                        t1 = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                        tmp_mic = t1.name
                        t1.close()
                        write_wav(tmp_mic, mic, samplerate, 1)
                    if sysa is not None and sysa.size > 0:
                        t2 = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                        tmp_sys = t2.name
                        t2.close()
                        write_wav(tmp_sys, sysa, samplerate, 1)
                    if ffmpeg and tmp_mic and tmp_sys:
                        try:
                            flt = f"[1:a]volume={self.mic_gain:.3f}[a1];[2:a]volume={self.sys_gain:.3f}[a2];[a1][a2]amix=inputs=2:duration=shortest:normalize=1"
                            cmd = [
                                ffmpeg, "-y",
                                "-i", tmp_video_path,
                                "-i", tmp_mic,
                                "-i", tmp_sys,
                                "-filter_complex", flt,
                                "-c:v", "copy",
                                "-c:a", "aac",
                                "-shortest",
                                path,
                            ]
                            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            audio_combined = True
                            os.unlink(tmp_video_path)
                            os.unlink(tmp_mic)
                            os.unlink(tmp_sys)
                        except Exception:
                            audio_combined = False
                    elif ffmpeg and (tmp_mic or tmp_sys):
                        one = tmp_mic or tmp_sys
                        try:
                            g = self.mic_gain if tmp_mic else self.sys_gain
                            cmd = [
                                ffmpeg, "-y",
                                "-i", tmp_video_path,
                                "-i", one,
                                "-filter:a", f"volume={g:.3f}",
                                "-c:v", "copy",
                                "-c:a", "aac",
                                "-shortest",
                                path,
                            ]
                            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            audio_combined = True
                            os.unlink(tmp_video_path)
                            os.unlink(one)
                        except Exception:
                            audio_combined = False
                elif audio_data is not None and audio_data.size > 0 and ffmpeg:
                    tmp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                    tmp_audio_path = tmp_audio.name
                    tmp_audio.close()
                    write_wav(tmp_audio_path, audio_data, samplerate, channels)
                    try:
                        g = self.mic_gain if self.audio_mode == "mic" else (self.sys_gain if self.audio_mode == "system" else 1.0)
                        cmd = [
                            ffmpeg, "-y",
                            "-i", tmp_video_path,
                            "-i", tmp_audio_path,
                            "-filter:a", f"volume={g:.3f}",
                            "-c:v", "copy",
                            "-c:a", "aac",
                            "-shortest",
                            path,
                        ]
                        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        audio_combined = True
                        os.unlink(tmp_video_path)
                        os.unlink(tmp_audio_path)
                    except Exception:
                        audio_combined = False
            except Exception:
                audio_combined = False

        if save_ok and not audio_combined:
            try:
                if os.path.exists(path):
                    os.unlink(path)
                os.replace(tmp_video_path, path)
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"移动文件失败：{e}")
                QMessageBox.information(self, "临时保留", f"视频临时文件保留在：{tmp_video_path}")
                return

        if save_ok:
            QMessageBox.information(self, "完成", "视频已保存")
            self.statusBar().showMessage("已保存")

        # 重置状态
        self.frames = []
        self.start_time = None
        self._update_title()

    def _toggle_audio(self, checked: bool):
        self.audio_enabled = bool(checked)
        msg = "开始录制时将采集麦克风音频" if self.audio_enabled else "将仅录制视频"
        self.statusBar().showMessage(msg, 3000)




# ----- Tray App -----

class FastCapApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("FastCap")
        self.setWindowIcon(create_app_icon())
        # 关闭任何窗口都不退出主程序（托盘常驻）
        self.setQuitOnLastWindowClosed(False)
        self._windows = []   # 保持已打开窗口的强引用
        self._overlays = []  # 保持选择覆盖层的强引用
        self._workers = []   # 保持线程/任务的强引用
        
        # 滚动截图模式：默认浏览器模式
        self.scroll_mode_browser = True


        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, "错误", "系统托盘不可用")
            sys.exit(1)

        self.tray = QSystemTrayIcon(create_app_icon(), self)
        menu = QMenu()

        act_region = QAction("区域截图", self)
        act_region.triggered.connect(self.capture_region_flow)
        act_region.setShortcut("Ctrl+Alt+R")
        menu.addAction(act_region)

        act_full = QAction("全屏截图", self)
        act_full.triggered.connect(self.capture_full_flow)
        act_full.setShortcut("Ctrl+Alt+F")
        menu.addAction(act_full)

        # 滚动截图
        act_scroll = QAction("滚动截图", self)
        act_scroll.triggered.connect(self.capture_scroll_flow)
        act_scroll.setShortcut("Ctrl+Alt+S")
        menu.addAction(act_scroll)
        
        # 滚动截图模式选择子菜单
        scroll_mode_menu = QMenu("滚动截图模式")
        
        self.act_mode_browser = QAction("浏览器模式", self)
        self.act_mode_browser.setCheckable(True)
        self.act_mode_browser.setChecked(True)  # 默认选中
        self.act_mode_browser.triggered.connect(self.set_scroll_mode_browser)
        scroll_mode_menu.addAction(self.act_mode_browser)
        
        self.act_mode_native = QAction("非浏览器模式", self)
        self.act_mode_native.setCheckable(True)
        self.act_mode_native.setChecked(False)
        self.act_mode_native.triggered.connect(self.set_scroll_mode_native)
        scroll_mode_menu.addAction(self.act_mode_native)
        
        menu.addMenu(scroll_mode_menu)

        act_record = QAction("屏幕录像（区域）", self)
        act_record.triggered.connect(self.record_region_flow)
        act_record.setShortcut("Ctrl+Alt+V")
        menu.addAction(act_record)

        act_pin = QAction("截图并复制（区域）", self)
        act_pin.triggered.connect(self.pin_region_flow)
        act_pin.setShortcut("Ctrl+Alt+P")
        menu.addAction(act_pin)

        menu.addSeparator()

        act_exit = QAction("退出", self)
        act_exit.triggered.connect(self.quit)
        act_exit.setShortcut("Ctrl+Alt+Q")
        menu.addAction(act_exit)

        self.tray.setContextMenu(menu)
        self.tray.setToolTip("FastCap 截图与标注")
        self.tray.show()

        # 注册全局快捷键（Windows）
        self._hk_registered = []
        self._hk_handlers = {}
        self._hk_filter = None
        try:
            self._init_global_hotkeys()
        except Exception:
            pass
        try:
            self.aboutToQuit.connect(self._unregister_hotkeys)
        except Exception:
            pass

    # OCR 相关已移除
    # def _set_ocr_lang(self, lang: str): pass
    # def _choose_tesseract_path(self): pass

    def capture_full_flow(self):
        pix = capture_all_monitors()
        editor = EditorWindow(pix)
        self._windows.append(editor)
        editor.show()

    def capture_region_flow(self):
        # 叠加层使用 Qt 合成的 1:1 逻辑坐标底图，避免放大
        pix = capture_all_monitors_overlay()
        overlay = SelectionOverlay(pix)
        overlay.captured.connect(self._open_editor)
        self._overlays.append(overlay)
        overlay.show()
        overlay.raise_()
        overlay.activateWindow()

    def _open_editor(self, pixmap: QPixmap):
        editor = EditorWindow(pixmap)
        self._windows.append(editor)
        editor.show()

    def set_scroll_mode_browser(self):
        """设置为浏览器模式"""
        self.scroll_mode_browser = True
        self.act_mode_browser.setChecked(True)
        self.act_mode_native.setChecked(False)

    def set_scroll_mode_native(self):
        """设置为非浏览器模式"""
        self.scroll_mode_browser = False
        self.act_mode_browser.setChecked(False)
        self.act_mode_native.setChecked(True)

    def capture_scroll_flow(self):
        """根据当前模式执行滚动截图"""
        if self.scroll_mode_browser:
            self.capture_scroll_browser_flow()
        else:
            self.capture_scroll_native_flow()

    def capture_scroll_browser_flow(self):
        """浏览器模式滚动截图"""
        pix = capture_all_monitors_overlay()
        overlay = SelectionOverlay(pix)
        overlay.captured_rect.connect(self._run_scroll_browser_capture)
        self._overlays.append(overlay)
        overlay.show()
        overlay.raise_()
        overlay.activateWindow()

    def _run_scroll_browser_capture(self, rect: QRect):
        self.tray.showMessage("滚动截图 - 浏览器模式", "开始自动滚动与拼接…")
        worker = ScrollWorker(rect, self)
        self._workers.append(worker)
        worker.finished.connect(lambda frames: self._open_editor(stitch_vertical(frames)))
        worker.start()

    def capture_scroll_native_flow(self):
        """非浏览器模式滚动截图"""
        pix = capture_all_monitors_overlay()
        overlay = SelectionOverlay(pix)
        overlay.captured_rect.connect(self._run_scroll_native_capture)
        self._overlays.append(overlay)
        overlay.show()
        overlay.raise_()
        overlay.activateWindow()

    def _run_scroll_native_capture(self, rect: QRect):
        self.tray.showMessage("滚动截图 - 非浏览器模式", "开始自动滚动与拼接…\n使用Page Down键滚动")
        worker = NativeScrollWorker(rect, self)
        self._workers.append(worker)
        worker.finished.connect(lambda frames: self._open_editor(stitch_vertical_native(frames)))
        worker.start()

    def record_region_flow(self):
        pix = capture_all_monitors_overlay()
        overlay = SelectionOverlay(pix)
        overlay.captured_rect.connect(lambda rect: self._open_recorder(rect))
        self._overlays.append(overlay)
        overlay.show()
        overlay.raise_()
        overlay.activateWindow()

    def _open_recorder(self, rect: QRect):
        win = RecorderWindow(rect)
        self._windows.append(win)
        win.show()

    def pin_region_flow(self):
        pix = capture_all_monitors_overlay()
        overlay = SelectionOverlay(pix)
        overlay.captured.connect(lambda p: self._pin_and_store(p))
        self._overlays.append(overlay)
        overlay.show()
        overlay.raise_()
        overlay.activateWindow()

    def _pin_and_store(self, p: QPixmap):
        # 选区贴图改为直接复制到剪贴板
        try:
            p.setDevicePixelRatio(1.0)
        except Exception:
            pass
        QGuiApplication.clipboard().setPixmap(p)
        # 可选提示：托盘气泡提示已复制
        try:
            if hasattr(self, 'tray') and isinstance(self.tray, QSystemTrayIcon):
                self.tray.showMessage("已复制", "选区已复制到剪贴板")
        except Exception:
            pass

    # def ocr_region_flow(self): pass

    # def _run_ocr(self, pix: QPixmap): pass

    # def _configure_tesseract(self): pass

    # ----- Global Hotkeys (Windows) -----
    def _init_global_hotkeys(self):
        if not sys.platform.startswith("win"):
            return

        # 定义热键 ID
        HK_REGION = 1
        HK_FULL = 2
        HK_SCROLL = 3
        HK_RECORD = 4
        HK_PIN = 5
        # 退出热键可选，默认不注册以避免与其他应用冲突
        HK_EXIT = 6

        MOD_ALT = 0x0001
        MOD_CONTROL = 0x0002
        MOD_SHIFT = 0x0004

        # 虚拟键码
        VK = {
            'R': 0x52,
            'F': 0x46,
            'S': 0x53,
            'V': 0x56,
            'P': 0x50,
            'Q': 0x51,
        }

        # 事件过滤器
        class WinHotkeyFilter(QAbstractNativeEventFilter):
            def __init__(self, handlers):
                super().__init__()
                self._handlers = handlers

            def nativeEventFilter(self, eventType, message):
                try:
                    et = bytes(eventType).decode(errors='ignore') if hasattr(eventType, 'data') or isinstance(eventType, (bytes, bytearray)) else str(eventType)
                except Exception:
                    et = str(eventType)
                if 'windows' not in et:
                    return False, 0
                WM_HOTKEY = 0x0312
                class MSG(ctypes.Structure):
                    _fields_ = [
                        ("hwnd", wintypes.HWND),
                        ("message", wintypes.UINT),
                        ("wParam", wintypes.WPARAM),
                        ("lParam", wintypes.LPARAM),
                        ("time", wintypes.DWORD),
                        ("pt", wintypes.POINT),
                    ]
                try:
                    msg = ctypes.cast(int(message), ctypes.POINTER(MSG)).contents
                except Exception:
                    return False, 0
                if msg.message == WM_HOTKEY:
                    hk_id = int(msg.wParam)
                    handler = self._handlers.get(hk_id)
                    if handler:
                        try:
                            handler()
                        except Exception:
                            pass
                        return True, 0
                return False, 0

        self._hk_filter = WinHotkeyFilter(self._hk_handlers)
        try:
            self.installNativeEventFilter(self._hk_filter)
        except Exception:
            self._hk_filter = None

        def _reg(id_, mod, vk, handler):
            ok = ctypes.windll.user32.RegisterHotKey(None, id_, mod, vk)
            if ok:
                self._hk_registered.append(id_)
                self._hk_handlers[id_] = handler
            else:
                try:
                    self.tray.showMessage("快捷键注册失败", f"热键 ID {id_} 可能与其他程序冲突")
                except Exception:
                    pass

        # 注册 Ctrl+Alt+R/F/S/V/P
        _reg(HK_REGION, MOD_CONTROL | MOD_ALT, VK['R'], self.capture_region_flow)
        _reg(HK_FULL,   MOD_CONTROL | MOD_ALT, VK['F'], self.capture_full_flow)
        _reg(HK_SCROLL, MOD_CONTROL | MOD_ALT, VK['S'], self.capture_scroll_flow)
        _reg(HK_RECORD, MOD_CONTROL | MOD_ALT, VK['V'], self.record_region_flow)
        _reg(HK_PIN,    MOD_CONTROL | MOD_ALT, VK['P'], self.pin_region_flow)
        # 全局退出快捷键不默认注册，避免与其他程序冲突

    def _unregister_hotkeys(self):
        if not sys.platform.startswith("win"):
            return
        for id_ in list(self._hk_registered):
            try:
                ctypes.windll.user32.UnregisterHotKey(None, id_)
            except Exception:
                pass
        self._hk_registered.clear()


def main():
    app = FastCapApp(sys.argv)
    sys.exit(app.exec())
# ----- Image helpers -----

# def qimage_to_pil(qimg: QImage) -> Image.Image: pass


def qpixmap_to_np_rgb(pix: QPixmap) -> np.ndarray:
    img = pix.toImage().convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    buf = img.bits()
    try:
        raw = buf.tobytes()
    except Exception:
        try:
            buf.setsize(img.byteCount())  # type: ignore
            raw = bytes(buf)
        except Exception:
            line_bytes = img.bytesPerLine()
            raw = b"".join(bytes(img.scanLine(i))[:line_bytes] for i in range(h))
    arr = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 4))
    rgb = arr[:, :, :3]
    return rgb.copy()

# def _otsu_threshold(gray_arr: np.ndarray) -> int: pass
    return t

# def preprocess_for_ocr(pil_img: Image.Image, mode: str = "auto") -> Image.Image: pass


def find_vertical_overlap(img1: np.ndarray, img2: np.ndarray, max_overlap: int = 300) -> int:
    h1, w1 = img1.shape[:2]
    h2, w2 = img2.shape[:2]
    w = min(w1, w2)
    a = img1[:, :w]
    b = img2[:, :w]
    a_gray = np.mean(a, axis=2)
    b_gray = np.mean(b, axis=2)
    best_off = 0
    best_err = float('inf')
    max_overlap = min(max_overlap, h1, h2)
    # 从0开始搜索，以适配各种滚动步长
    for off in range(0, max_overlap):
        a_strip = a_gray[h1 - off : h1, :]
        b_strip = b_gray[0 : off, :]
        if a_strip.shape != b_strip.shape:
            continue
        err = np.mean(np.abs(a_strip - b_strip))
        if err < best_err:
            best_err = err
            best_off = off
    return best_off

def _find_vertical_overlap_cv(img1: np.ndarray, img2: np.ndarray) -> int:
    if cv2 is None:
        return 0
    try:
        a = img1
        b = img2
        h1, w1 = a.shape[:2]
        h2, w2 = b.shape[:2]
        w = min(w1, w2)
        a = a[:, :w]
        b = b[:, :w]
        ga = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
        gb = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
        try:
            sift = cv2.SIFT_create()
        except Exception:
            sift = None
        if sift is None:
            try:
                orb = cv2.ORB_create(1200)
            except Exception:
                return 0
            ka, da = orb.detectAndCompute(ga, None)
            kb, db = orb.detectAndCompute(gb, None)
            if da is None or db is None or len(ka) < 8 or len(kb) < 8:
                return 0
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(da, db)
            if not matches:
                return 0
            pts_a = np.float32([ka[m.queryIdx].pt for m in matches])
            pts_b = np.float32([kb[m.trainIdx].pt for m in matches])
        else:
            ka, da = sift.detectAndCompute(ga, None)
            kb, db = sift.detectAndCompute(gb, None)
            if da is None or db is None or len(ka) < 8 or len(kb) < 8:
                return 0
            index_params = dict(algorithm=1, trees=5)
            search_params = dict(checks=50)
            flann = cv2.FlannBasedMatcher(index_params, search_params)
            matches = flann.knnMatch(da, db, k=2)
            good = []
            for m in matches:
                if len(m) == 2:
                    if m[0].distance < 0.6 * m[1].distance:
                        good.append(m[0])
            if len(good) < 8:
                return 0
            pts_a = np.float32([ka[m.queryIdx].pt for m in good])
            pts_b = np.float32([kb[m.trainIdx].pt for m in good])
        if len(pts_a) < 6:
            return 0
        A, inliers = cv2.estimateAffine2D(pts_a, pts_b)
        if A is None:
            H, inliers = cv2.findHomography(pts_a, pts_b, cv2.RANSAC, 5.0)
            if H is None:
                return 0
            dy = H[1, 2]
        else:
            dy = A[1, 2]
        off = int(round(max(0, dy)))
        if off <= 0:
            diffs = pts_b[:, 1] - pts_a[:, 1]
            off = int(round(max(0, float(np.median(diffs)))))
        return off
    except Exception:
        return 0

def _jam_overlap(img1: np.ndarray, img2: np.ndarray):
    if cv2 is None:
        return 0, 0, 0, 0
    try:
        h1, w1 = img1.shape[:2]
        h2, w2 = img2.shape[:2]
        w = min(w1, w2)
        a = img1[:, :w]
        b = img2[:, :w]
        ga = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
        gb = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
        try:
            sift = cv2.SIFT_create()
        except Exception:
            return 0, 0, 0, 0
        kps1, des1 = sift.detectAndCompute(ga, None)
        kps2, des2 = sift.detectAndCompute(gb, None)
        if des1 is None or des2 is None or len(kps1) < 4 or len(kps2) < 4:
            return 0, 0, 0, 0
        index_params = dict(algorithm=1, trees=5)
        search_params = dict(checks=64)
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        matches = flann.knnMatch(des1, des2, k=2)
        goods = []
        for m in matches:
            if len(m) == 2 and m[0].distance < 0.6 * m[1].distance:
                q = kps1[m[0].queryIdx].pt
                t = kps2[m[0].trainIdx].pt
                ig_top = int(min(h1, h2) * 0.05)
                ig_bot = int(min(h1, h2) * 0.05)
                if (ig_top <= q[1] <= h1 - ig_bot) and (ig_top <= t[1] <= h2 - ig_bot):
                    goods.append(m[0])
        if len(goods) < 4:
            return 0, 0, 0, len(goods)
        freq = {}
        for g in goods:
            dy = int(round(kps1[g.queryIdx].pt[1] - kps2[g.trainIdx].pt[1]))
            if abs(dy) > max(h1, h2):
                continue
            freq[dy] = freq.get(dy, 0) + 1
        if not freq:
            return 0, 0, 0, len(goods)
        distancesmode = max(freq.items(), key=lambda kv: kv[1])[0]
        max1y = 0.0
        max2y = 0.0
        for g in goods:
            pos0 = kps1[g.queryIdx].pt
            pos1 = kps2[g.trainIdx].pt
            if int(pos0[1] - pos1[1]) == distancesmode:
                if pos0[1] > max1y:
                    max1y = pos0[1]
                if pos1[1] > max2y:
                    max2y = pos1[1]
        off = int(max(0, distancesmode))
        c1 = int(min(h1, max1y))
        c2 = int(min(h2, max2y))
        return off, c1, c2, len(goods)
    except Exception:
        return 0, 0, 0, 0
def _edge_strength(rgb: np.ndarray, y0: int, y1: int) -> float:
    h, w = rgb.shape[:2]
    y0 = max(0, min(h - 1, y0))
    y1 = max(0, min(h, y1))
    if y1 <= y0:
        return 0.0
    blk = rgb[y0:y1, :min(w, 2048), :]
    g = blk.astype(np.float32)
    gx = np.abs(g[:, 1:, :] - g[:, :-1, :]).mean()
    gy = np.abs(g[1:, :, :] - g[:-1, :, :]).mean()
    return float(gx + gy)

def _col_sampling(img_array: np.ndarray, cols_group: list[list[int]] | None = None) -> np.ndarray:
    g = np.mean(img_array.astype(np.float32), axis=2)
    h, w = g.shape
    grad = np.zeros_like(g)
    if h > 1:
        grad[1:, :] = np.abs(g[1:, :] - g[:-1, :])
    if not cols_group:
        span = max(1, w // 48)
        centers = [int(w * r) for r in [0.1, 0.25, 0.4, 0.55, 0.7, 0.85]]
        cols_group = [[max(0, c - span), min(w - 1, c + span)] for c in centers]
    cols_luma = []
    cols_grad = []
    for g0 in cols_group:
        s = max(0, min(w - 1, int(g0[0])))
        e = max(s + 1, min(w, int(g0[1]) + 1))
        cols_luma.append(np.mean(g[:, s:e], axis=1))
        cols_grad.append(np.mean(grad[:, s:e], axis=1))
    return np.concatenate([np.stack(cols_luma, axis=1), np.stack(cols_grad, axis=1)], axis=1)

def _predict_offset(max_abs: int, p: int) -> list[int]:
    p = int(max(0, min(max_abs, p)))
    seq = [p]
    d = 1
    while d <= max_abs and len(seq) < max_abs + 1:
        a = p + d
        b = p - d
        if a <= max_abs:
            seq.append(a)
        if b >= 0:
            seq.append(b)
        d += 1
    return seq

def _diff_overlap(cols: np.ndarray, cols2: np.ndarray, predict: int = 0, approx_diff: float = 0.2, min_overlap: int = 120) -> tuple[int, float]:
    h1 = cols.shape[0]
    h2 = cols2.shape[0]
    m = min(h1, h2) - 1
    cand = _predict_offset(m, predict)
    best_off = 0
    best_err = 1e9
    tried = 0
    for off in cand:
        a = cols[h1 - off : h1, :]
        b = cols2[0 : off, :]
        if a.shape != b.shape or a.size == 0:
            continue
        ig = max(1, min(off // 12, 24))
        a2 = a[ig : off - ig, :]
        b2 = b[ig : off - ig, :]
        if a2.shape != b2.shape or a2.size == 0:
            continue
        err_cols = np.mean(np.abs(a2 - b2), axis=0)
        err = float(np.median(err_cols))
        tried += 1
        if err < best_err:
            best_err = err
            best_off = int(off)
        if err <= approx_diff and tried >= 10:
            break
    if best_off < min_overlap:
        return 0, best_err
    return best_off, best_err

def _splice_pair(a: np.ndarray, b: np.ndarray, off: int) -> np.ndarray:
    h1 = a.shape[0]
    w = min(a.shape[1], b.shape[1])
    a = a[:, :w]
    b = b[:, :w]
    cut_a = max(0, h1 - off)
    bo = a[cut_a:h1]
    co = b[0:off]
    H = bo.shape[0]
    W = bo.shape[1]
    if H == 0 or W == 0:
        return np.vstack([a, b])
    diff = np.mean(np.abs(bo - co), axis=2)
    dp = np.zeros_like(diff)
    ptr = np.zeros((H, W), dtype=np.int16)
    dp[:, 0] = diff[:, 0]
    for j in range(1, W):
        prev = dp[:, j - 1]
        m0 = prev
        m1 = np.concatenate((np.array([1e9], dtype=prev.dtype), prev[:-1]))
        m2 = np.concatenate((prev[1:], np.array([1e9], dtype=prev.dtype)))
        stack = np.stack([m0, m1, m2], axis=0)
        idx = np.argmin(stack, axis=0)
        dp[:, j] = diff[:, j] + np.min(stack, axis=0)
        ptr[:, j] = idx.astype(np.int16) - 1
    path = np.zeros(W, dtype=np.int32)
    i = int(np.argmin(dp[:, W - 1]))
    path[W - 1] = i
    for j in range(W - 1, 0, -1):
        i = i + int(ptr[i, j])
        if i < 0:
            i = 0
        elif i >= H:
            i = H - 1
        path[j - 1] = i
    ov = np.empty((H, W, 3), dtype=np.float32)
    bl = max(6, min(24, off // 10))
    for j in range(W):
        s = int(path[j])
        t0 = max(0, s - bl // 2)
        t1 = min(H, s + bl // 2)
        if t0 > 0:
            ov[:t0, j, :] = bo[:t0, j, :]
        if t1 < H:
            ov[t1:, j, :] = co[t1:, j, :]
        if t1 > t0:
            r = np.arange(t0, t1, dtype=np.float32)
            alpha = (t1 - r) / max(1.0, float(t1 - t0))
            alpha = alpha.reshape(-1, 1)
            ov[t0:t1, j, :] = bo[t0:t1, j, :] * alpha + co[t0:t1, j, :] * (1.0 - alpha)
    head = a[: cut_a, :W]
    tail = b[off:, :W]
    out = np.vstack([head, ov, tail]).astype(np.uint8)
    return out

def stitch_vertical(pixes: list[QPixmap]) -> QPixmap:
    if not pixes:
        return QPixmap()
    arrays = [qpixmap_to_np_rgb(p) for p in pixes]
    base = arrays[0]
    cols_base = _col_sampling(base)
    ideal = 0
    for cur in arrays[1:]:
        cols_cur = _col_sampling(cur)
        if ideal <= 0:
            off0, err0 = _diff_overlap(cols_base, cols_cur, predict=min(cols_base.shape[0], cols_cur.shape[0]) // 2, approx_diff=0.18, min_overlap=80)
            ideal = int(off0)
        else:
            off0, err0 = _diff_overlap(cols_base, cols_cur, predict=ideal, approx_diff=0.18, min_overlap=max(80, int(ideal * 0.6)))
            if off0 <= 0:
                off0, err0 = _diff_overlap(cols_base, cols_cur, predict=min(cols_base.shape[0], cols_cur.shape[0]) // 2, approx_diff=0.22, min_overlap=60)
        if off0 <= 0:
            base = np.vstack([base, cur])
        else:
            base = _splice_pair(base, cur, off0)
        cols_base = _col_sampling(base)
        if off0 > 0:
            try:
                ideal = int(0.7 * ideal + 0.3 * off0)
            except Exception:
                ideal = int(off0)
    h, w = base.shape[:2]
    qimg = QImage(base.data, w, h, w * 3, QImage.Format_RGB888)
    pix = QPixmap.fromImage(qimg.copy())
    try:
        dpr = float(getattr(pixes[0], 'devicePixelRatio', lambda: 1.0)())
        if dpr < 1.0:
            dpr = 1.0
        pix.setDevicePixelRatio(dpr)
    except Exception:
        pass
    return pix


def stitch_vertical_native(pixes: list[QPixmap]) -> QPixmap:
    """
    非浏览器模式的拼接函数 - 使用更精确的重叠检测
    适用于使用Page Down滚动的原生应用
    """
    if not pixes:
        return QPixmap()
    
    if len(pixes) == 1:
        return pixes[0]
    
    # 首先过滤掉重复的帧
    arrays = [qpixmap_to_np_rgb(p) for p in pixes]
    filtered_arrays = [arrays[0]]
    
    for i in range(1, len(arrays)):
        cur = arrays[i]
        last = filtered_arrays[-1]
        
        # 检查当前帧是否与上一帧几乎相同
        if cur.shape == last.shape:
            diff = np.mean(np.abs(cur.astype(np.float32) - last.astype(np.float32)))
            # 如果差异很小，跳过这一帧
            if diff < 1.0:
                continue
        
        filtered_arrays.append(cur)
    
    # 如果过滤后只剩一帧，直接返回
    if len(filtered_arrays) == 1:
        return pixes[0]
    
    base = filtered_arrays[0]
    
    for idx, cur in enumerate(filtered_arrays[1:], 1):
        h_base = base.shape[0]
        h_cur = cur.shape[0]
        w = min(base.shape[1], cur.shape[1])
        
        # 确保宽度一致
        base = base[:, :w]
        cur = cur[:, :w]
        
        # 寻找最佳重叠区域 - 使用更精细的搜索
        best_overlap = 0
        best_score = float('inf')
        
        # 搜索范围：从较小的重叠开始，到较大的重叠
        # Page Down通常会滚动大约80-90%的屏幕高度
        min_search = max(20, int(h_cur * 0.05))  # 至少5%的当前帧高度
        max_search = min(int(h_cur * 0.95), h_base - 20)  # 最多95%的当前帧高度
        
        # 使用较小的步长以获得更精确的匹配
        step = max(2, (max_search - min_search) // 100)
        
        for overlap in range(min_search, max_search, step):
            try:
                # 比较base的底部和cur的顶部
                base_bottom = base[-overlap:, :, :]
                cur_top = cur[:overlap, :, :]
                
                if base_bottom.shape != cur_top.shape:
                    continue
                
                # 使用多种指标综合评估匹配度
                # 1. 像素差异
                pixel_diff = np.mean(np.abs(base_bottom.astype(np.float32) - cur_top.astype(np.float32)))
                
                # 2. 结构相似性（简化版）- 比较边缘
                base_edges = np.abs(np.diff(base_bottom.astype(np.float32), axis=0)).mean()
                cur_edges = np.abs(np.diff(cur_top.astype(np.float32), axis=0)).mean()
                edge_diff = abs(base_edges - cur_edges)
                
                # 综合评分：像素差异权重更高
                score = pixel_diff + edge_diff * 0.1
                
                if score < best_score:
                    best_score = score
                    best_overlap = overlap
                    
                # 如果找到非常好的匹配（像素差异小于1.5），提前退出
                if pixel_diff < 1.5:
                    break
            except Exception:
                continue
        
        # 精细调整：在最佳重叠附近进行更细致的搜索
        if best_overlap > 0:
            fine_min = max(min_search, best_overlap - step * 2)
            fine_max = min(max_search, best_overlap + step * 2)
            for overlap in range(fine_min, fine_max):
                try:
                    base_bottom = base[-overlap:, :, :]
                    cur_top = cur[:overlap, :, :]
                    
                    if base_bottom.shape != cur_top.shape:
                        continue
                    
                    pixel_diff = np.mean(np.abs(base_bottom.astype(np.float32) - cur_top.astype(np.float32)))
                    
                    if pixel_diff < best_score:
                        best_score = pixel_diff
                        best_overlap = overlap
                except Exception:
                    continue
        
        # 如果找到了合理的重叠（差异小于阈值）
        if best_overlap > 0 and best_score < 30.0:
            # 使用简单的alpha混合进行拼接
            overlap_region = best_overlap
            
            # 创建混合区域
            base_part = base[-overlap_region:, :, :].astype(np.float32)
            cur_part = cur[:overlap_region, :, :].astype(np.float32)
            
            # 线性混合 - 从base渐变到cur
            alpha = np.linspace(1, 0, overlap_region).reshape(-1, 1, 1)
            blended = (base_part * alpha + cur_part * (1 - alpha)).astype(np.uint8)
            
            # 拼接：base的前部分 + 混合区域 + cur的后部分
            base = np.vstack([
                base[:-overlap_region, :, :],
                blended,
                cur[overlap_region:, :, :]
            ])
        else:
            # 如果没有找到好的重叠，使用保守策略
            # 假设Page Down滚动了大约85%的屏幕
            estimated_overlap = int(h_cur * 0.15)
            if estimated_overlap > 0 and estimated_overlap < h_base:
                # 简单拼接，去掉估计的重叠部分
                base = np.vstack([base[:-estimated_overlap, :, :], cur])
            else:
                # 直接拼接
                base = np.vstack([base, cur])
    
    # 转换回QPixmap
    h, w = base.shape[:2]
    qimg = QImage(base.data, w, h, w * 3, QImage.Format_RGB888)
    pix = QPixmap.fromImage(qimg.copy())
    
    try:
        dpr = float(getattr(pixes[0], 'devicePixelRatio', lambda: 1.0)())
        if dpr < 1.0:
            dpr = 1.0
        pix.setDevicePixelRatio(dpr)
    except Exception:
        pass
    
    return pix

if __name__ == "__main__":
    main()