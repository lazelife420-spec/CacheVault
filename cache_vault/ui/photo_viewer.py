"""Desktop Photo Viewer top-level window for viewing image clips with zoom/pan and navigation."""

from __future__ import annotations

import io
import tkinter as tk
from typing import Any, Callable
import customtkinter as ctk
from PIL import Image, ImageTk

from .. import brand
from . import theme


class PhotoViewer(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        initial_clip_id: str,
        all_clip_ids: list[str],
        get_clip_fn: Callable[[str], Any],
        load_asset_fn: Callable[[str], tuple[bytes, str] | None],
        asset_meta_fn: Callable[[str], dict | None],
        copy_image_fn: Callable[[str], None],
        save_image_as_fn: Callable[[str], None],
        open_asset_folder_fn: Callable[[str], None],
    ):
        super().__init__(master)
        self.title(f"{brand.PRODUCT_NAME} — Photo Viewer")
        self.geometry("900x700")
        self.minsize(600, 450)
        self.configure(fg_color="#0a0a0a")

        self._get_clip_fn = get_clip_fn
        self._load_asset_fn = load_asset_fn
        self._asset_meta_fn = asset_meta_fn
        self._copy_image_fn = copy_image_fn
        self._save_image_as_fn = save_image_as_fn
        self._open_asset_folder_fn = open_asset_folder_fn

        # Filter all_clip_ids to get only image clips in order
        self._image_ids = []
        for cid in all_clip_ids:
            clip = self._get_clip_fn(cid)
            if clip and getattr(clip, "content_type", None) == "IMAGE":
                self._image_ids.append(cid)

        # Fallback if initial_clip_id is not in the filtered list
        if initial_clip_id not in self._image_ids:
            self._image_ids.insert(0, initial_clip_id)

        try:
            self._current_index = self._image_ids.index(initial_clip_id)
        except ValueError:
            self._current_index = 0

        # PIL Image references for current image
        self._pil_image: Image.Image | None = None
        self._photo_image: ImageTk.PhotoImage | None = None

        # Zoom & Pan State
        self._zoom_factor: float = 1.0
        self._offset_x: float = 0.0
        self._offset_y: float = 0.0
        self._drag_start_x: float = 0.0
        self._drag_start_y: float = 0.0
        # True until the canvas has had its first real Configure event with valid size
        self._is_first_load: bool = True
        # Whether the last intentional zoom action was "fit" (used for double-click toggle)
        self._is_fitted: bool = True

        self._setup_ui()
        self._setup_bindings()
        self._load_image()

    # ------------------------------------------------------------------ #
    # UI setup
    # ------------------------------------------------------------------ #

    def _setup_ui(self) -> None:
        # Main layout: Canvas in middle, toolbar at bottom
        self._canvas = tk.Canvas(self, bg="#0a0a0a", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)

        # Bottom control panel
        self._toolbar = ctk.CTkFrame(self, height=50, fg_color="#121212", corner_radius=0)
        self._toolbar.pack(fill="x", side="bottom")

        # Navigation container (left)
        self._nav_frame = ctk.CTkFrame(self._toolbar, fg_color="transparent")
        self._nav_frame.pack(side="left", padx=10, pady=5)

        self._btn_prev = ctk.CTkButton(
            self._nav_frame, text="◀ Prev", width=70, height=28,
            command=self._prev_image, **theme.secondary_button()
        )
        self._btn_prev.pack(side="left", padx=2)

        self._info_label = ctk.CTkLabel(
            self._nav_frame, text="0 / 0", font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ffffff", width=80
        )
        self._info_label.pack(side="left", padx=5)

        self._btn_next = ctk.CTkButton(
            self._nav_frame, text="Next ▶", width=70, height=28,
            command=self._next_image, **theme.secondary_button()
        )
        self._btn_next.pack(side="left", padx=2)

        # Zoom container (centre)
        self._zoom_frame = ctk.CTkFrame(self._toolbar, fg_color="transparent")
        self._zoom_frame.pack(side="left", expand=True, pady=5)

        ctk.CTkButton(
            self._zoom_frame, text="Fit", width=50, height=28,
            command=self._zoom_fit, **theme.secondary_button()
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            self._zoom_frame, text="1:1", width=50, height=28,
            command=self._zoom_reset, **theme.secondary_button()
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            self._zoom_frame, text="Zoom −", width=70, height=28,
            command=self._zoom_out, **theme.secondary_button()
        ).pack(side="left", padx=2)

        self._zoom_label = ctk.CTkLabel(
            self._zoom_frame, text="100%", font=ctk.CTkFont(size=12),
            text_color="#aaaaaa", width=50
        )
        self._zoom_label.pack(side="left", padx=2)

        ctk.CTkButton(
            self._zoom_frame, text="Zoom +", width=70, height=28,
            command=self._zoom_in, **theme.secondary_button()
        ).pack(side="left", padx=2)

        # Actions container (right — reused copy, save, folder)
        self._actions_frame = ctk.CTkFrame(self._toolbar, fg_color="transparent")
        self._actions_frame.pack(side="right", padx=10, pady=5)

        ctk.CTkButton(
            self._actions_frame, text="Copy", width=60, height=28,
            command=self._action_copy, **theme.secondary_button()
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            self._actions_frame, text="Save As", width=70, height=28,
            command=self._action_save, **theme.secondary_button()
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            self._actions_frame, text="Folder", width=60, height=28,
            command=self._action_folder, **theme.secondary_button()
        ).pack(side="left", padx=2)

    # ------------------------------------------------------------------ #
    # Bindings
    # ------------------------------------------------------------------ #

    def _setup_bindings(self) -> None:
        # Drag to pan
        self._canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self._canvas.bind("<B1-Motion>", self._on_drag_motion)

        # Double-click canvas: toggle Fit ↔ 1:1
        self._canvas.bind("<Double-Button-1>", self._on_double_click)

        # Canvas resize listener
        self._canvas.bind("<Configure>", lambda e: self._on_resize())

        # Mouse-wheel zoom (Windows sends <MouseWheel> with delta multiples of 120)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        # Linux/X11 fallback
        self._canvas.bind("<Button-4>", lambda e: self._zoom_in())
        self._canvas.bind("<Button-5>", lambda e: self._zoom_out())

        # Keyboard shortcuts
        self.bind("<Left>", lambda e: self._prev_image())
        self.bind("<Right>", lambda e: self._next_image())
        self.bind("<plus>", lambda e: self._zoom_in())
        self.bind("<equal>", lambda e: self._zoom_in())
        self.bind("<minus>", lambda e: self._zoom_out())
        self.bind("<f>", lambda e: self._zoom_fit())
        self.bind("<F>", lambda e: self._zoom_fit())
        self.bind("<Escape>", lambda e: self.destroy())

    # ------------------------------------------------------------------ #
    # Event handlers
    # ------------------------------------------------------------------ #

    def _on_drag_start(self, event: tk.Event) -> None:
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag_motion(self, event: tk.Event) -> None:
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y
        self._offset_x += dx
        self._offset_y += dy
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        self._is_fitted = False
        self._draw_image()

    def _on_double_click(self, event: tk.Event) -> None:
        """Toggle between Fit and 1:1 zoom on canvas double-click."""
        if self._is_fitted:
            self._zoom_reset()
        else:
            self._zoom_fit()

    def _on_mousewheel(self, event: tk.Event) -> None:
        """Zoom in/out on Windows mouse-wheel scroll."""
        if event.delta > 0:
            self._zoom_in()
        else:
            self._zoom_out()

    def _on_resize(self) -> None:
        """On canvas resize: only re-draw (not re-fit) to avoid a second fit flash.

        The initial fit is triggered by _load_image → _zoom_fit when
        _is_first_load is True and the canvas already has real dimensions.
        After that, resize events just re-centre the existing zoom level.
        """
        if self._is_first_load:
            # Canvas may not have real dimensions yet on very first event;
            # only commit the first-load fit if canvas is properly sized.
            w = self._canvas.winfo_width()
            h = self._canvas.winfo_height()
            if w > 10 and h > 10 and self._pil_image is not None:
                self._zoom_fit()
                self._is_first_load = False
        else:
            self._draw_image()

    # ------------------------------------------------------------------ #
    # Navigation helpers
    # ------------------------------------------------------------------ #

    def _get_current_clip_id(self) -> str | None:
        if 0 <= self._current_index < len(self._image_ids):
            return self._image_ids[self._current_index]
        return None

    def _update_nav_state(self) -> None:
        """Always update nav label and button states, even on load failure."""
        count = len(self._image_ids)
        self._info_label.configure(text=f"{self._current_index + 1} / {count}")
        self._btn_prev.configure(state="normal" if self._current_index > 0 else "disabled")
        self._btn_next.configure(state="normal" if self._current_index < count - 1 else "disabled")

    def _update_title(self) -> None:
        """Set window title to include current clip display name if available."""
        clip_id = self._get_current_clip_id()
        if clip_id:
            clip = self._get_clip_fn(clip_id)
            name = getattr(clip, "display_name", None) or getattr(clip, "source_app", None)
            if name:
                self.title(f"{brand.PRODUCT_NAME} — Photo Viewer — {name}")
                return
        self.title(f"{brand.PRODUCT_NAME} — Photo Viewer")

    # ------------------------------------------------------------------ #
    # Image loading & drawing
    # ------------------------------------------------------------------ #

    def _load_image(self) -> None:
        clip_id = self._get_current_clip_id()
        if not clip_id:
            self._pil_image = None
            self._draw_placeholder("No image selected.")
            self._update_nav_state()
            return

        loaded = self._load_asset_fn(clip_id)
        if not loaded:
            self._pil_image = None
            self._draw_placeholder("Image file unavailable.")
            self._update_nav_state()
            self._update_title()
            return

        png_bytes, _mime = loaded
        try:
            self._pil_image = Image.open(io.BytesIO(png_bytes))
            if self._is_first_load:
                # Let _on_resize trigger the first fit once the canvas is measured.
                # If canvas already has real dimensions (e.g. on navigation), fit now.
                w = self._canvas.winfo_width()
                h = self._canvas.winfo_height()
                if w > 10 and h > 10:
                    self._zoom_fit()
                    self._is_first_load = False
            else:
                self._zoom_fit()
        except Exception:
            self._pil_image = None
            self._draw_placeholder("Failed to load image.")

        self._update_nav_state()
        self._update_title()

    def _draw_placeholder(self, text: str) -> None:
        self._canvas.delete("all")
        self._canvas.create_text(
            self._canvas.winfo_width() / 2,
            self._canvas.winfo_height() / 2,
            text=text, fill="#ff6b6b", font=("Segoe UI", 14, "bold")
        )

    def _draw_image(self) -> None:
        if not self._pil_image:
            return

        w = max(10, self._canvas.winfo_width())
        h = max(10, self._canvas.winfo_height())

        img_w, img_h = self._pil_image.size
        target_w = max(1, int(img_w * self._zoom_factor))
        target_h = max(1, int(img_h * self._zoom_factor))

        try:
            resized_img = self._pil_image.resize((target_w, target_h), Image.Resampling.BILINEAR)
            self._photo_image = ImageTk.PhotoImage(resized_img)

            self._canvas.delete("all")
            self._canvas.create_image(
                w / 2 + self._offset_x,
                h / 2 + self._offset_y,
                image=self._photo_image,
                anchor="center"
            )
            self._zoom_label.configure(text=f"{int(self._zoom_factor * 100)}%")
        except Exception:
            self._draw_placeholder("Error scaling image.")

    # ------------------------------------------------------------------ #
    # Zoom controls
    # ------------------------------------------------------------------ #

    def _zoom_fit(self) -> None:
        if not self._pil_image:
            return
        w = max(10, self._canvas.winfo_width())
        h = max(10, self._canvas.winfo_height())
        img_w, img_h = self._pil_image.size

        margin = 20
        scale_w = (w - margin) / img_w
        scale_h = (h - margin) / img_h
        self._zoom_factor = min(scale_w, scale_h, 1.0)
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._is_fitted = True
        self._draw_image()

    def _zoom_reset(self) -> None:
        """Set zoom to 1:1 (100%)."""
        self._zoom_factor = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._is_fitted = False
        self._draw_image()

    def _zoom_in(self) -> None:
        self._zoom_factor = min(self._zoom_factor * 1.2, 5.0)
        self._is_fitted = False
        self._draw_image()

    def _zoom_out(self) -> None:
        self._zoom_factor = max(self._zoom_factor / 1.2, 0.05)
        self._is_fitted = False
        self._draw_image()

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #

    def _prev_image(self) -> None:
        if self._current_index > 0:
            self._current_index -= 1
            self._load_image()

    def _next_image(self) -> None:
        if self._current_index < len(self._image_ids) - 1:
            self._current_index += 1
            self._load_image()

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def _action_copy(self) -> None:
        clip_id = self._get_current_clip_id()
        if clip_id:
            self._copy_image_fn(clip_id)

    def _action_save(self) -> None:
        clip_id = self._get_current_clip_id()
        if clip_id:
            self._save_image_as_fn(clip_id)

    def _action_folder(self) -> None:
        clip_id = self._get_current_clip_id()
        if clip_id:
            self._open_asset_folder_fn(clip_id)

    def present(self) -> None:
        self.deiconify()
        self.focus_force()
