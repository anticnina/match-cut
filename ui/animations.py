"""Animation helpers for MatchCut UI."""

from PyQt6.QtCore import (
    QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup,
    QParallelAnimationGroup, QPoint, QTimer, pyqtProperty,
)
from PyQt6.QtWidgets import QWidget, QMainWindow, QGraphicsOpacityEffect


def fade_in(widget: QWidget, duration: int = 700, delay: int = 0) -> QPropertyAnimation:
    """Fade in a widget. Uses windowOpacity for top-level windows (avoids black-window bug on Windows)."""
    if isinstance(widget, QMainWindow) or widget.isWindow():
        widget.setWindowOpacity(0.0)
        anim = QPropertyAnimation(widget, b"windowOpacity")
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutSine)
        if delay:
            QTimer.singleShot(delay, anim.start)
        else:
            anim.start()
        widget._fade_anim = anim
        return anim

    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutSine)
    if delay:
        QTimer.singleShot(delay, anim.start)
    else:
        anim.start()
    widget._fade_anim = anim
    return anim


def fade_out(widget: QWidget, duration: int = 500, callback=None) -> QPropertyAnimation:
    """Fade out a widget. Uses windowOpacity for top-level windows."""
    if isinstance(widget, QMainWindow) or widget.isWindow():
        anim = QPropertyAnimation(widget, b"windowOpacity")
        anim.setDuration(duration)
        anim.setStartValue(widget.windowOpacity())
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InSine)
        if callback:
            anim.finished.connect(callback)
        anim.start()
        widget._fade_anim = anim
        return anim

    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.Type.InSine)
    if callback:
        anim.finished.connect(callback)
    anim.start()
    widget._fade_anim = anim
    return anim


def slide_up_fade_in(widget: QWidget, duration: int = 800, delay: int = 0):
    """Fade in while translating upward 24px."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    opacity_anim = QPropertyAnimation(effect, b"opacity")
    opacity_anim.setDuration(duration)
    opacity_anim.setStartValue(0.0)
    opacity_anim.setEndValue(1.0)
    opacity_anim.setEasingCurve(QEasingCurve.Type.OutSine)

    pos_anim = QPropertyAnimation(widget, b"pos")
    pos_anim.setDuration(duration)
    start_pos = widget.pos() + QPoint(0, 24)
    pos_anim.setStartValue(start_pos)
    pos_anim.setEndValue(widget.pos())
    pos_anim.setEasingCurve(QEasingCurve.Type.OutSine)

    group = QParallelAnimationGroup(widget)
    group.addAnimation(opacity_anim)
    group.addAnimation(pos_anim)

    if delay:
        QTimer.singleShot(delay, group.start)
    else:
        group.start()
    return group


def staggered_entrance(widgets: list[QWidget], base_delay: int = 0, step: int = 200):
    """Animate each widget with slide_up_fade_in, staggered."""
    anims = []
    for i, w in enumerate(widgets):
        a = slide_up_fade_in(w, duration=840, delay=base_delay + i * step)
        anims.append(a)
    return anims
