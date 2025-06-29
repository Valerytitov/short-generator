# Финальная, исправленная версия animate_code.py
import os
from pathlib import Path
from manim import *
import glob
from typing import List

# --- ШАГ 1: ГЛОБАЛЬНАЯ НАСТРОЙКА (выполняется при импорте файла) ---
# Читаем разрешение из переменной окружения, которую задает bot.py
resolution_str = os.environ.get("RESOLUTION", "1080,1920")
pixel_width, pixel_height = map(int, resolution_str.split(','))

# Устанавливаем глобальную конфигурацию Manim ДО запуска сцены. Это самый надежный способ.
config.pixel_width = pixel_width
config.pixel_height = pixel_height
config.frame_rate = 30
# Указываем, чтобы Manim не добавлял свои флаги к имени файла, т.к. мы задаем его точно
# config.output_file = Path(os.environ.get("OUTPUT_FILE", "video_only.mp4")).stem

def split_text_to_fit(text: str, max_width: float, font: str = "Arial", weight=BOLD) -> str:
    words = text.split()
    lines: List[str] = []
    current_line = ""
    for word in words:
        test_line = (current_line + " " + word).strip()
        test_mob = Text(test_line, font=font, weight=weight)
        if test_mob.width <= max_width or not current_line:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return "\n".join(lines)

class CodeScene(Scene):
    def __init__(self, **kwargs):
        # Получаем остальные данные из переменных окружения
        self.code_str = os.environ.get("CODE_TEXT", "")
        self.top_text = os.environ.get("TOP_TEXT", "")
        self.bottom_text = os.environ.get("BOTTOM_TEXT", "")
        super().__init__(**kwargs)

    def construct(self):
        # --- ШАГ 2: ВНУТРИСЦЕНОВАЯ НАСТРОЙКА КАМЕРЫ (условная) ---
        # Проверяем, является ли видео вертикальным (ширина < высота)
        if config.pixel_width < config.pixel_height:
            # Применяем "магические" настройки из старого рабочего скрипта для 9:16
            self.camera.frame_width = 9
            self.camera.frame_height = 16
        
        # --- ШАГ 3: ЛОГИКА РЕНДЕРИНГА (без изменений) ---
        if self.top_text:
            top_text_wrapped = split_text_to_fit(self.top_text, self.camera.frame_width * 0.95, font="Arial", weight=BOLD)
            top_text_mob = Text(top_text_wrapped, font="Arial", weight=BOLD)
            top_text_mob.scale_to_fit_width(self.camera.frame_width * 0.95)
            max_top_height = self.camera.frame_height * 0.15
            if top_text_mob.height > max_top_height:
                top_text_mob.scale_to_fit_height(max_top_height)
            # Центрируем по X, прижимаем к верху с небольшим отступом
            top_text_mob.move_to([0, self.camera.frame_height/2 - top_text_mob.height/2 - 0.2, 0])
            self.add(top_text_mob)
        else:
            top_text_mob = Text("", font="Arial", weight=BOLD)

        if self.bottom_text:
            bottom_text_wrapped = split_text_to_fit(self.bottom_text, self.camera.frame_width * 0.95, font="Arial")
            bottom_text_mob = Text(bottom_text_wrapped, font="Arial").scale(0.8)
            bottom_text_mob.scale_to_fit_width(self.camera.frame_width * 0.95)
            max_bottom_height = self.camera.frame_height * 0.15
            if bottom_text_mob.height > max_bottom_height:
                bottom_text_mob.scale_to_fit_height(max_bottom_height)
            # Центрируем по X, прижимаем к низу с небольшим отступом
            bottom_text_mob.move_to([0, -self.camera.frame_height/2 + bottom_text_mob.height/2 + 0.2, 0])
            self.add(bottom_text_mob)
        else:
            bottom_text_mob = Text("", font="Arial").scale(0.8)
        
        # Определяем доступное пространство для кода между надписями
        code_top_y = top_text_mob.get_bottom()[1] - 0.5 if self.top_text else self.camera.frame_height / 2 - 0.5
        code_bottom_y = bottom_text_mob.get_top()[1] + 0.5 if self.bottom_text else -self.camera.frame_height / 2 + 0.5
        available_height = code_top_y - code_bottom_y
        available_width = self.camera.frame_width * 0.9

        # Создаем объект кода
        code = Code(
            code_string=self.code_str,
            language="python"
        )
        
        # Масштабируем код, чтобы он поместился в доступное пространство
        if code.width > available_width:
            code.scale_to_fit_width(available_width)
        if code.height > available_height:
            code.scale_to_fit_height(available_height)
            
        # Центрируем код в доступном пространстве
        center_point = np.array([0, code_bottom_y + available_height / 2, 0])
        code.move_to(center_point)

        animation_time = 5
        audio_duration = float(os.environ.get("AUDIO_DURATION", "7"))
        self.play(Write(code), run_time=animation_time)
        self.wait(max(0, audio_duration - animation_time))
        # [MANIM DEBUG] Выводим путь итогового видео
        print(f"[MANIM DEBUG] Итоговое видео: {self.renderer.file_writer.movie_file_path}")

# Функция main() и argparse полностью удалены, так как они не нужны и создавали проблемы.

for f in glob.glob("media/videos/animate_code/**/*.mp4", recursive=True):
    print(f"[MANIM DEBUG] Найден mp4: {f}")