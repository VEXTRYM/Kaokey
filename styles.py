from PySide6.QtWidgets import (
    QProxyStyle,
    QStyle,
    QStyleHintReturn,
    QStyleOption,
    QWidget,
)

from style_constants import (
    TOOLTIP_DELAY,
)


class KaokeyStyle(QProxyStyle):
    def styleHint(
        self,
        hint: QStyle.StyleHint,
        option: QStyleOption | None = None,
        widget: QWidget | None = None,
        returnData: QStyleHintReturn | None = None,
    ) -> int:
        if (
            hint
            == QStyle.StyleHint.SH_ToolTip_WakeUpDelay
        ):
            return TOOLTIP_DELAY

        return super().styleHint(
            hint,
            option,
            widget,
            returnData,
        )