from __future__ import annotations

from pathlib import Path
from perception.screenshot import annotate_screenshot, capture_screenshot
from perception.ui_tree import build_ui_tree, collect_interactive_elements
from perception.windows import enumerate_windows, get_active_window, get_cursor_position


def main():
	cursor = get_cursor_position()
	windows = enumerate_windows()
	active = get_active_window()

	ui_tree = build_ui_tree(windows, active_window=active)
	elements = collect_interactive_elements(ui_tree) if ui_tree else []

	screenshot = capture_screenshot()
	annotated = annotate_screenshot(screenshot, elements, cursor)

	out_dir = Path("artifacts")
	out_dir.mkdir(parents=True, exist_ok=True)
	out_path = out_dir / "annotated_preview.png"
	annotated.save(out_path)

	print(f"Saved: {out_path.resolve()}")
	print(f"Elements annotated: {len(elements)}")
	print(f"Cursor position: {cursor}")


if __name__ == "__main__":
	main()