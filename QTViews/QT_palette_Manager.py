from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


class QTPaletteManager:
    """
    Gestisce la QPalette globale dell'applicazione Qt.

    La palette di sistema resta la base: gli override modificano solo i
    ruoli dichiarati, lasciando al tema Qt/OS tutto il resto.
    """

    ROLE_BY_NAME = {
        "window": QPalette.ColorRole.Window,
        "window-text": QPalette.ColorRole.WindowText,
        "base": QPalette.ColorRole.Base,
        "alternate-base": QPalette.ColorRole.AlternateBase,
        "tool-tip-base": QPalette.ColorRole.ToolTipBase,
        "tool-tip-text": QPalette.ColorRole.ToolTipText,
        "placeholder-text": QPalette.ColorRole.PlaceholderText,
        "text": QPalette.ColorRole.Text,
        "button": QPalette.ColorRole.Button,
        "button-text": QPalette.ColorRole.ButtonText,
        "bright-text": QPalette.ColorRole.BrightText,
        "light": QPalette.ColorRole.Light,
        "midlight": QPalette.ColorRole.Midlight,
        "mid": QPalette.ColorRole.Mid,
        "dark": QPalette.ColorRole.Dark,
        "shadow": QPalette.ColorRole.Shadow,
        "highlight": QPalette.ColorRole.Highlight,
        "highlighted-text": QPalette.ColorRole.HighlightedText,
        "link": QPalette.ColorRole.Link,
        "link-visited": QPalette.ColorRole.LinkVisited,
    }

    GROUP_BY_NAME = {
        "active": QPalette.ColorGroup.Active,
        "inactive": QPalette.ColorGroup.Inactive,
        "disabled": QPalette.ColorGroup.Disabled,
    }

    DEFAULT_OVERRIDES = {
        "highlight": "#2659ab",
        "highlighted-text": "#ffffff",
        "button-text": "#ffffff",
        "mid": "#c2c2c2"
    }

    APP_STYLESHEET = """
        QPushButton {                           
            background-color: palette(button);
            color: palette(button-text);
            border: 1px solid palette(highlight);
            border-radius: 4px;
            padding: 5px 10px;
        }

        QPushButton:hover {
            border-color: palette(light);
        }

        QPushButton:pressed {
            background-color: palette(dark);
            border-color: palette(highlight);
        }

        QPushButton:disabled {
            background-color: palette(window);
            color: palette(mid);
            border-color: palette(mid);
        }

        QLineEdit {
            background-color: palette(base);
            color: palette(text);
            border: none;
            border-bottom: 1px solid palette(midlight);
            padding: 4px 2px;
        }

        QLineEdit:focus {
            border-bottom: 2px solid palette(highlight);
        }
        
        QTextEdit {
            background-color: palette(base);
            color: palette(text);
            border: none;
            border-bottom: 1px solid palette(midlight);
            padding: 4px 2px;
        }
        
        QTextEdit:focus {
            border-bottom: 2px solid palette(highlight);
        }
        
        QTFilterableComboBox {
            background-color: palette(base);
            color: palette(text);
            border: none;
            border-bottom: 1px solid palette(midlight);
            padding: 4px 2px;
        }
        
        QTFilterableComboBox:focus {
            border-bottom: 2px solid palette(highlight);
        }

        QComboBox QAbstractItemView {
            selection-background-color: palette(highlight);
            selection-color: palette(highlighted-text);
            outline: 0;
        }

        QComboBox QAbstractItemView::item:selected {
            background-color: palette(highlight);
            color: palette(highlighted-text);
            border-left: 3px solid palette(highlight);
        }

        QToolTip {
            background-color: palette(midlight);
            color: palette(text);
            border: 1px solid palette(mid);
            padding: 4px 6px;
        }
    """

    def __init__(self, app: QApplication | None = None):
        self.app = app or QApplication.instance()
        if self.app is None:
            raise RuntimeError("QTPaletteManager richiede una QApplication attiva.")

        self._system_palette = QPalette(self.app.palette())
        self._palette = QPalette(self._system_palette)
        self._system_stylesheet = self.app.styleSheet()

    @classmethod
    def install(
        cls,
        app: QApplication | None = None,
        overrides: Mapping[str, str | QColor] | None = None,
    ) -> "QTPaletteManager":
        manager = cls(app)
        manager.apply(cls.DEFAULT_OVERRIDES if overrides is None else overrides)
        return manager

    def apply(self, overrides: Mapping[str, str | QColor] | None = None) -> None:
        self._palette = QPalette(self._system_palette)
        if overrides:
            self.set_colors(overrides, apply_now=False)
        self.app.setPalette(self._palette)
        self.app.setStyleSheet(self._merged_stylesheet())

    def reset_to_system(self) -> None:
        self._palette = QPalette(self._system_palette)
        self.app.setPalette(self._palette)
        self.app.setStyleSheet(self._system_stylesheet)

    def set_color(
        self,
        role_name: str,
        color: str | QColor,
        group_name: str | None = None,
        apply_now: bool = True,
    ) -> None:
        role = self._role(role_name)
        qt_color = QColor(color)
        if not qt_color.isValid():
            raise ValueError(f"Colore Qt non valido: {color!r}")

        if group_name is None:
            self._palette.setColor(role, qt_color)
        else:
            self._palette.setColor(self._group(group_name), role, qt_color)

        if apply_now:
            self.app.setPalette(self._palette)

    def set_colors(
        self,
        colors: Mapping[str, str | QColor],
        group_name: str | None = None,
        apply_now: bool = True,
    ) -> None:
        for role_name, color in colors.items():
            self.set_color(role_name, color, group_name=group_name, apply_now=False)

        if apply_now:
            self.app.setPalette(self._palette)

    def color_name(self, role_name: str, group_name: str = "active") -> str:
        return self._palette.color(self._group(group_name), self._role(role_name)).name()

    def snapshot(self) -> dict[str, dict[str, str]]:
        return {
            group_name: {
                role_name: self._palette.color(group, role).name()
                for role_name, role in self.ROLE_BY_NAME.items()
            }
            for group_name, group in self.GROUP_BY_NAME.items()
        }

    def print_snapshot(self) -> None:
        for group_name, colors in self.snapshot().items():
            print(f"\n[{group_name}]")
            for role_name, color in colors.items():
                print(f"{role_name}: {color}")

    def _merged_stylesheet(self) -> str:
        if not self._system_stylesheet.strip():
            return self.APP_STYLESHEET
        return f"{self._system_stylesheet}\n{self.APP_STYLESHEET}"

    @classmethod
    def _role(cls, role_name: str) -> QPalette.ColorRole:
        normalized = role_name.strip().lower().replace("_", "-")
        try:
            return cls.ROLE_BY_NAME[normalized]
        except KeyError as exc:
            valid = ", ".join(cls.ROLE_BY_NAME)
            raise KeyError(f"Ruolo palette non valido: {role_name!r}. Validi: {valid}") from exc

    @classmethod
    def _group(cls, group_name: str) -> QPalette.ColorGroup:
        normalized = group_name.strip().lower().replace("_", "-")
        try:
            return cls.GROUP_BY_NAME[normalized]
        except KeyError as exc:
            valid = ", ".join(cls.GROUP_BY_NAME)
            raise KeyError(f"Gruppo palette non valido: {group_name!r}. Validi: {valid}") from exc
