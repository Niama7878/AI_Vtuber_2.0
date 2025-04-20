import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
import pygame
import threading
import time
import OpenGL.GL as gl
import freetype
import ctypes

class ChatDisplay:
    def __init__(self, width=1400, height=240, font_path="ShanHaiNiuNaiBoBoW-2.ttf", backup_file="backup.txt", font_size=60, typing_speed=0.12):
        """初始化参数"""
        self.width = width
        self.height = height
        self.font_path = font_path
        self.font_size = font_size
        self.typing_speed = typing_speed

        self.face = freetype.Face(font_path)
        self.face.set_char_size(font_size * 64)

        self.text_queue = ""
        self.display_text = ""
        self.lines = []
        self.char_index = 0
        self.last_char_time = time.time()
        self.full_text_rendered_time = None
        self.lock = threading.Lock()
        self.char_width_cache = {} # 缓存字符宽度，减少重复计算
        self.running = True # 运行状态

        self.backup_file = backup_file

        threading.Thread(target=self._pygame_loop, daemon=True).start()
        threading.Thread(target=self._monitor_backup_file, daemon=True).start()

    def update_text(self, text):
        """添加文本到显示队列"""
        with self.lock:
            if self.text_queue:
                self.text_queue += text
            else:
                self.text_queue = text
            self.full_text_rendered_time = None

    def _monitor_backup_file(self):
        """监听 backup.txt 并读取内容显示"""
        open(self.backup_file, 'a', encoding='utf-8').close()
        with open(self.backup_file, 'r+', encoding='utf-8') as f:
            while self.running:
                content = f.read().strip()
                if content:
                    self.update_text(content)
                    f.seek(0)
                    f.truncate() # 清空内容
                time.sleep(0.01)
                
    def _pygame_loop(self):
        """Pygame 事件和 OpenGL 渲染循环"""
        pygame.init() 
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.OPENGL | pygame.DOUBLEBUF | pygame.NOFRAME)
        pygame.display.set_caption("聊天信息显示框")
        self.hwnd = pygame.display.get_wm_info()["window"] # 获取窗口句柄
        self.texture_id = gl.glGenTextures(1) # 生成 OpenGL 纹理 id

        gl.glViewport(0, 0, self.width, self.height)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        gl.glOrtho(0, self.width, self.height, 0, -1, 1)
        gl.glClearColor(0.0, 1.0, 0.0, 1.0) # 初始清屏颜色设置为绿色

        clock = pygame.time.Clock()
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._move_window()

            self._render_text()
            pygame.display.flip()
            clock.tick(30)
            time.sleep(0.01)
        pygame.quit()

    def _move_window(self):
        """拖动无边框窗口 (仅限 Windows)"""
        ctypes.windll.user32.ReleaseCapture()
        ctypes.windll.user32.SendMessageW(self.hwnd, 0xA1, 2, 0)

    def _render_text(self):
        """模拟打字效果，同时管理文本显示时间"""
        current_time = time.time()
        with self.lock:
            if self.char_index < len(self.text_queue) and current_time - self.last_char_time > self.typing_speed:
                self.char_index += 1
                self.display_text = self.text_queue[:self.char_index]
                self.lines = self._wrap_text(self.display_text)
                self.last_char_time = current_time

                if self.char_index == len(self.text_queue):
                    self.full_text_rendered_time = current_time

            # 保持屏幕内显示的行数
            max_lines = self.height // self.font_size
            while len(self.lines) > max_lines:
                self.lines.pop(0)
                self.display_text = "\n".join(self.lines)

            if self.full_text_rendered_time and current_time - self.full_text_rendered_time > 8: # 完全显示后超时无新文本
                self.text_queue = ""
                self.display_text = ""
                self.lines = []
                self.char_index = 0
                self.full_text_rendered_time = None

        # 设置绿色背景并清屏
        gl.glClearColor(0.0, 1.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        y_offset = 0
        for line in self.lines:
            line_width = self._get_text_width(line)
            x_start_offset = (self.width - line_width) / 2  # 居中对齐
            x_offset = x_start_offset
            for char in line:
                self._render_char(char, x_offset, y_offset)
                x_offset += self.char_width_cache.get(char, self._get_text_width(char))
            y_offset += self.font_size

    def _get_text_width(self, text):
        """计算字符串宽度，利用缓存减少重复计算"""
        width = 0
        for char in text:
            if char in self.char_width_cache:
                char_width = self.char_width_cache[char]
            else:
                self.face.load_char(char, freetype.FT_LOAD_RENDER)
                char_width = self.face.glyph.linearHoriAdvance / 65536.0
                self.char_width_cache[char] = char_width
            width += char_width
        return width

    def _render_char(self, char, x, y):
        """渲染单个字符，将其位图转换为纹理并绘制到 (x, y)"""
        self.face.load_char(char, freetype.FT_LOAD_RENDER)
        glyph = self.face.glyph
        bitmap = glyph.bitmap
        width, height = bitmap.width, bitmap.rows

        if width == 0 or height == 0:
            return

        rgba_buffer = bytearray()
    
        for value in bitmap.buffer:
            alpha = value
            if alpha > 0:
                rgba_buffer.extend([255, 191, 204, alpha])
            else:
                rgba_buffer.extend([0, 0, 0, 0])

        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, bytes(rgba_buffer))
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glBegin(gl.GL_QUADS)
        gl.glTexCoord2f(0, 0)
        gl.glVertex2f(x, y)
        gl.glTexCoord2f(1, 0)
        gl.glVertex2f(x + width, y)
        gl.glTexCoord2f(1, 1)
        gl.glVertex2f(x + width, y + height)
        gl.glTexCoord2f(0, 1)
        gl.glVertex2f(x, y + height)
        gl.glEnd()
        gl.glDisable(gl.GL_TEXTURE_2D)
        gl.glDisable(gl.GL_BLEND)

    def _wrap_text(self, text):
        """根据窗口宽度自动换行"""
        lines = []
        current_line = ""
        for char in text:
            test_line = current_line + char
            if self._get_text_width(test_line) > self.width - 100:
                lines.append(current_line)
                current_line = char
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
        return lines
    
display = ChatDisplay()
while display.running:
    time.sleep(1)