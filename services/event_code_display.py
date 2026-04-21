from __future__ import annotations


def build_code_panel_html(code_str: str) -> str:
    return f"""
<div id="code-display-panel" style="
    text-align: center;
    padding: 2.5rem 1rem;
    background: #0e1117;
    border: 2px solid #2d2d3a;
    border-radius: 1rem;
    margin: 1rem 0;
">
    <p style="
        color: #888;
        font-size: 1rem;
        margin: 0 0 0.5rem 0;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    ">Active Code</p>
    <p id="code-display-value" style="
        font-size: 7rem;
        font-weight: 900;
        letter-spacing: 0.35em;
        color: #ffffff;
        margin: 0;
        font-family: monospace;
        line-height: 1;
    ">{code_str}</p>
</div>
"""


def build_fullscreen_code_html(code_str: str) -> str:
    return f"""
<div style="
    text-align: center;
    padding: 4rem 2rem;
    background: #0e1117;
    border-radius: 1rem;
">
    <p style="
        color: #888;
        font-size: 1.2rem;
        margin: 0 0 1rem 0;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    ">Active Code</p>
    <p style="
        font-size: 20rem;
        font-weight: 900;
        letter-spacing: 0.4em;
        color: #ffffff;
        margin: 0;
        font-family: monospace;
        line-height: 1;
    ">{code_str}</p>
</div>
"""
