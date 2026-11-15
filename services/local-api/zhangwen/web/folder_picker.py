"""A fixed, short-lived Windows folder chooser, isolated from API worker threads."""
import json


def main():
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    try:
        path = filedialog.askdirectory(parent=root, title='请选择同一个掌问项目文件夹', mustexist=True)
        print(json.dumps({'path': path}, ensure_ascii=True), flush=True)
    finally:
        root.destroy()


if __name__ == '__main__':
    main()
