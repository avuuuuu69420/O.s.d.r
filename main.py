"""Entry point for GSSE26 Discord Rich Presence."""

from dependencies import prepare_dependencies


def main():
    # Bootstrap required/optional packages before importing the GUI module.
    prepare_dependencies()

    from app import GSSE26RPC
    import tkinter as tk

    root = tk.Tk()
    GSSE26RPC(root)
    root.mainloop()


if __name__ == "__main__":
    main()
