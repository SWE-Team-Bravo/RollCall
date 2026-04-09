from io import BytesIO
from typing import cast
import pandas as pd
from pandas._typing import WriteExcelBuffer


def to_excel(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(cast(WriteExcelBuffer, buf), engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()
