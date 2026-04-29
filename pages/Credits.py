import streamlit as st
import streamlit.components.v1 as components

# Hide Streamlit chrome and stretch the component iframe to fill the viewport
st.markdown(
    """
<style>
    footer, #MainMenu,
    header[data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    .stDeployButton { display: none !important; }

    [data-testid="stSidebar"],
    [data-testid="stSidebarCollapsedControl"] { display: none !important; }

    [data-testid="stAppViewContainer"],
    [data-testid="block-container"],
    .main .block-container { padding: 0 !important; max-width: 100% !important; }

    iframe {
        position: fixed !important;
        top: 0 !important; left: 0 !important;
        width: 100vw !important; height: 100vh !important;
        border: none !important;
        z-index: 99999 !important;
    }
</style>
    """,
    unsafe_allow_html=True,
)

components.html(
    """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    background: #000;
    overflow: hidden;
    font-family: 'Georgia', 'Times New Roman', serif;
  }

  #reel {
    position: absolute;
    left: 0;
    right: 0;
    text-align: center;
    will-change: transform;
  }

  .title {
    font-size: 7rem;
    font-weight: 700;
    color: #fff;
    letter-spacing: 0.12em;
    line-height: 1;
    margin-bottom: 0.25em;
  }

  .subtitle {
    font-size: 1.5rem;
    color: #555;
    letter-spacing: 0.35em;
    text-transform: uppercase;
    margin-bottom: 8rem;
  }

  .section {
    font-size: 1rem;
    color: #444;
    letter-spacing: 0.5em;
    text-transform: uppercase;
    margin-bottom: 5rem;
  }

  .role {
    font-size: 1.4rem;
    color: #c9a84c;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    margin-bottom: 0.4em;
  }

  .name {
    font-size: 5.5rem;
    font-weight: 700;
    color: #fff;
    line-height: 1;
    margin-bottom: 0.2em;
  }

  .github {
    font-family: 'Courier New', monospace;
    font-size: 1.1rem;
    color: #444;
    margin-bottom: 5rem;
  }

  #back-btn {
    position: fixed;
    top: 1.2rem;
    left: 1.4rem;
    font-size: 0.95rem;
    color: #555;
    cursor: pointer;
    letter-spacing: 0.1em;
    user-select: none;
    z-index: 10;
    transition: color 0.2s;
  }
  #back-btn:hover { color: #aaa; }
</style>
</head>
<body>

<div id="back-btn" onclick="window.parent.history.back()">Back</div>

<div id="reel">

  <div class="title">RollCall</div>
  <div class="section">The Team</div>

  <div class="role">Product Owner</div>
  <div class="name">Charlie</div>
  <div class="github">github.com/cgale2</div>

  <div class="role">Backend Developer</div>
  <div class="name">Brent</div>
  <div class="github">github.com/Sqble</div>

  <div class="role">Developer</div>
  <div class="name">Huseyin</div>
  <div class="github">github.com/hsimsek1</div>

  <div class="role">Developer</div>
  <div class="name">Tati</div>
  <div class="github">github.com/tetkacheva</div>

  <div class="role">Developer</div>
  <div class="name">Elijah</div>
  <div class="github">github.com/elijahseif</div>

  <div class="role">Developer</div>
  <div class="name">Koussay</div>
  <div class="github">github.com/koussay0</div>

  <div class="role">Developer &amp; Logo Designer</div>
  <div class="name">Priyadharsan</div>
  <div class="github">github.com/PriyadharsanJayaseelan</div>

  <div class="role">Developer</div>
  <div class="name">TJ</div>
  <div class="github">github.com/Monster0506</div>


</div>

<script>
  let reel = document.getElementById('reel');
  let y = window.innerHeight;
  let speed = 2.5;

  (function tick() {
    y -= speed;
    if (y <= -reel.scrollHeight) {
      y = window.innerHeight;
    }
    reel.style.transform = 'translateY(' + y + 'px)';
    requestAnimationFrame(tick);
  })();
</script>

</body>
</html>
""",
    height=600,
    scrolling=False,
)
