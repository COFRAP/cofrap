import base64
from io import BytesIO

import qrcode


def qr_data_url(value: str) -> str:
    buffer = BytesIO()
    qrcode.make(value, box_size=6, border=4).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
