<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <title>연립정부 시뮬레이터</title>
    <!-- 엔진 최신 버전 및 폰트 깨짐 방지 -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stlite/mountable@latest/build/stlite.css" />
  </head>
  <body>
    <!-- 높이를 100vh로 강제하여 흰 화면 버그 방지 -->
    <div id="root" style="height: 100vh;"></div>
    
    <script src="https://cdn.jsdelivr.net/npm/@stlite/mountable@latest/build/stlite.js"></script>
    <script>
      stlite.mount(
        {
          requirements: ["pandas", "plotly", "numpy"],
          entrypoint: "app.py",
          files: {
            "app.py": {
              // 상대 경로 대신 깃허브 원본 파일 주소 강제 매핑
              url: "https://raw.githubusercontent.com/dgtaehyeon/Coalition-Government-Formation-Simulator/main/app.py"
            }
          }
        },
        document.getElementById("root")
      );
    </script>
  </body>
</html>
