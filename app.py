import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, Wedge, FancyBboxPatch, Rectangle
import numpy as np
import io
import zipfile
import os
import tempfile
import streamlit.components.v1 as components
from matplotlib.colors import to_rgba, to_rgb, LinearSegmentedColormap


# Helper function to lighten/darken a color (not used in D3.js, but kept for Matplotlib if needed elsewhere)
def adjust_lightness(color, amount=0.5):
    """
    Lightens or darkens a color.
    amount > 1.0 brightens, amount < 1.0 darkens.
    """
    try:
        c = to_rgb(color)
    except ValueError:
        c = to_rgba(color)[:3] # Handle rgba input too, take only rgb parts
    c = np.array(c)
    # This is a simple linear adjustment; for more perceptual lightness, convert to HSL/HSV
    if amount >= 1.0: # Lighten
        return tuple(c + (1 - c) * (amount - 1.0))
    else: # Darken
        return tuple(c * amount)


# Function to draw the ROUND gauge and return it as a BytesIO object (Matplotlib-based)
def create_gauge_image(
    value: int,
    size_x: int,
    size_y: int,
    active_color: str,
    inactive_color: str,
    bg_color: str,
    gauge_name: str,
    show_name: bool,
    show_value: bool,
    image_format: str,  # "png" or "jpeg"
    gauge_thickness_pixels: int,
    gauge_start_angle_deg: int,
    gauge_end_angle_deg: int,
    fill_direction: str,
    output_dpi: int,
    gauge_type: str,
    num_segments: int = 50,
    segment_gap_deg: float = 2.0,
    total_gauge_values: int = 100,
    is_3d: bool = False,
    gauge_value_color: str = "#FFFFFF",
    gauge_name_color: str = "#FFFFFF"
) -> io.BytesIO:
    """
    Generates a single ROUND gauge image for a given value based on selected gauge type.
    """
    fig, ax = plt.subplots(
        figsize=(size_x / output_dpi, size_y / output_dpi), dpi=output_dpi
    )
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect('equal')
    ax.axis('off')

    center_x, center_y = 0.5, 0.5
    min_dim = min(size_x, size_y)
    outer_diameter_pixels = max(1, min_dim - gauge_thickness_pixels)
    radius = (outer_diameter_pixels / 2) / min_dim
    gauge_line_width_points = gauge_thickness_pixels * (72.0 / output_dpi)

    # Calculate sweep degrees
    if fill_direction == "counter-clockwise":
        total_sweep_degrees_base = (gauge_end_angle_deg - gauge_start_angle_deg + 360) % 360
    else:
        total_sweep_degrees_base = (gauge_start_angle_deg - gauge_end_angle_deg + 360) % 360
    if total_sweep_degrees_base == 0 and gauge_start_angle_deg == gauge_end_angle_deg:
        total_sweep_degrees_base = 360

    current_fill_ratio = (
        value / (total_gauge_values - 1.0)
        if total_gauge_values > 1
        else 0.0
    )

    # Draw arcs (continuous or segmented)
    if gauge_type == "continuous":
        # Determine arc angles
        inactive_arc_theta1 = gauge_start_angle_deg if fill_direction == "counter-clockwise" else gauge_end_angle_deg
        inactive_arc_theta2 = gauge_end_angle_deg if fill_direction == "counter-clockwise" else gauge_start_angle_deg
        if value > 0 and total_sweep_degrees_base > 0:
            if fill_direction == "counter-clockwise":
                current_angle_on_circle = gauge_start_angle_deg + (current_fill_ratio * total_sweep_degrees_base)
                active_arc_theta1 = gauge_start_angle_deg
                active_arc_theta2 = current_angle_on_circle
            else:
                current_angle_on_circle = gauge_start_angle_deg - (current_fill_ratio * total_sweep_degrees_base)
                active_arc_theta1 = current_angle_on_circle
                active_arc_theta2 = gauge_start_angle_deg
        else:
            active_arc_theta1, active_arc_theta2 = gauge_start_angle_deg, gauge_start_angle_deg

        # 3D shadow layers
        if is_3d:
            num_shadow_layers = 5
            offset_factor = 0.0005 * radius
            active_rgb = to_rgb(active_color)
            inactive_rgb = to_rgb(inactive_color)
            active_gradient_colors = [tuple(c * (1 - 0.1 * i) for c in active_rgb) for i in range(num_shadow_layers + 1)]
            inactive_gradient_colors = [tuple(c * (1 - 0.1 * i) for c in inactive_rgb) for i in range(num_shadow_layers + 1)]
            for i in range(num_shadow_layers, -1, -1):
                ox = i * offset_factor
                oy = i * offset_factor
                ax.add_patch(Arc(
                    (center_x + ox, center_y - oy),
                    width=2 * radius,
                    height=2 * radius,
                    angle=0,
                    theta1=inactive_arc_theta1,
                    theta2=inactive_arc_theta2,
                    color=inactive_gradient_colors[i],
                    linewidth=gauge_line_width_points,
                    capstyle='round',
                    zorder=i
                ))
                if value > 0 and total_sweep_degrees_base > 0:
                    ax.add_patch(Arc(
                        (center_x + ox, center_y - oy),
                        width=2 * radius,
                        height=2 * radius,
                        angle=0,
                        theta1=active_arc_theta1,
                        theta2=active_arc_theta2,
                        color=active_gradient_colors[i],
                        linewidth=gauge_line_width_points,
                        capstyle='round',
                        zorder=i + 0.5
                    ))
        # Main arcs
        ax.add_patch(Arc(
            (center_x, center_y),
            width=2 * radius,
            height=2 * radius,
            angle=0,
            theta1=inactive_arc_theta1,
            theta2=inactive_arc_theta2,
            color=inactive_color,
            linewidth=gauge_line_width_points,
            capstyle='round',
            zorder=100
        ))
        if value > 0 and total_sweep_degrees_base > 0:
            ax.add_patch(Arc(
                (center_x, center_y),
                width=2 * radius,
                height=2 * radius,
                angle=0,
                theta1=active_arc_theta1,
                theta2=active_arc_theta2,
                color=active_color,
                linewidth=gauge_line_width_points,
                capstyle='round',
                zorder=101
            ))

    elif gauge_type == "segmented":
        total_effective_sweep = total_sweep_degrees_base - (num_segments * segment_gap_deg)
        single_segment_angle = max(0, total_effective_sweep / num_segments)
        num_active_segments = int(round(current_fill_ratio * num_segments))
        current_segment_angle = gauge_start_angle_deg
        for i in range(num_segments):
            segment_color = active_color if i < num_active_segments else inactive_color
            if fill_direction == "counter-clockwise":
                t1 = current_segment_angle
                t2 = current_segment_angle + single_segment_angle
            else:
                t1 = current_segment_angle - single_segment_angle
                t2 = current_segment_angle
            ax.add_patch(Arc(
                (center_x, center_y),
                width=2 * radius,
                height=2 * radius,
                angle=0,
                theta1=t1,
                theta2=t2,
                color=segment_color,
                linewidth=gauge_line_width_points,
                capstyle='butt'
            ))
            if fill_direction == "counter-clockwise":
                current_segment_angle += single_segment_angle + segment_gap_deg
            else:
                current_segment_angle -= single_segment_angle + segment_gap_deg

    # Add Gauge Name text if requested
    if show_name and gauge_name:
        ax.text(
            center_x,
            center_y + radius * 0.2,
            gauge_name,
            ha='center', va='center',
            color=gauge_name_color,
            fontsize=radius * 30,
            weight='bold',
            zorder=120
        )

    # Add Gauge Value text if requested
    if show_value:
        val_y = center_y if not (show_name and gauge_name) else center_y - radius * 0.1
        ax.text(
            center_x,
            val_y,
            f"{value}",
            ha='center', va='center',
            color=gauge_value_color,
            fontsize=radius * 40,
            weight='bold',
            zorder=120
        )

    plt.tight_layout(pad=0)
    buf = io.BytesIO()
    plt.savefig(
        buf,
        format=image_format,
        bbox_inches='tight',
        pad_inches=0,
        transparent=False,
        dpi=output_dpi
    )
    plt.close(fig)
    buf.seek(0)
    return buf
# Function to draw the LINEAR gauge and return it as a BytesIO object (Matplotlib-based)
def create_linear_gauge_image(
    value: int,
    size_x: int,
    size_y: int,
    active_color: str,
    inactive_color: str,
    bg_color: str,
    gauge_name: str,
    show_name: bool,
    show_value: bool,
    image_format: str,
    linear_thickness_pixels: int,
    orientation: str, # "horizontal" or "vertical"
    num_segments: int = 50,
    segment_gap_pixels: int = 2,
    tip_style: str = "Rounded",
    total_gauge_values: int = 100,
    output_dpi: int = 100,
    is_3d: bool = False, # Added 3D parameter for linear gauges
    gauge_value_color: str = "#FFFFFF", # New parameter for value text color
    gauge_name_color: str = "#FFFFFF" # New parameter for name text color
) -> io.BytesIO:
    """
    Generates a single LINEAR gauge image for a given value using Matplotlib.

    Args:
        value (int): The current value of the gauge (0-99).
        size_x (int): Width of the gauge image in pixels.
        size_y (int): Height of the gauge image in pixels.
        active_color (str): Hex code for the active part of the gauge.
        inactive_color (str): Hex code for the unfilled part of the gauge.
        bg_color (str): Hex code for the background of the image.
        gauge_name (str): The name text for the gauge.
        show_name (bool): Whether to display the gauge name.
        show_value (bool): Whether to display the current gauge value.
        image_format (str): The desired output image format ('png' or 'jpeg').
        linear_thickness_pixels (int): The thickness of the linear gauge bar in pixels.
        orientation (str): The orientation of the linear gauge ('horizontal' or 'vertical').
        num_segments (int): The total number of segments for a segmented gauge.
        segment_gap_pixels (int): The pixel gap between individual segments.
        tip_style (str): The style of the gauge tips ('Rounded' or 'Straight').
        total_gauge_values (int): The total number of distinct gauge values (e.g., 100 for 0-99).
        output_dpi (int): The DPI (Dots Per Inch) for rendering the image.
        is_3d (bool): If True, a subtle 3D "pop-out" effect will be added.
        gauge_value_color (str): Hex code for the gauge value text color.
        gauge_name_color (str): Hex code for the gauge name text color.

    Returns:
        io.BytesIO: A BytesIO object containing the generated image data.
    """
    fig, ax = plt.subplots(figsize=(size_x / output_dpi, size_y / output_dpi), dpi=output_dpi)
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')

    # Calculate padding based on the smaller dimension to ensure it's always relative
    min_dim_pixels = min(size_x, size_y)
    padding_pixels = min_dim_pixels * 0.1 # 10% padding
    
    # Convert padding and thickness to relative units for Matplotlib's transform=ax.transAxes
    padding_x_ratio = padding_pixels / size_x
    padding_y_ratio = padding_pixels / size_y

    bar_thickness_ratio_x = linear_thickness_pixels / size_x
    bar_thickness_ratio_y = linear_thickness_pixels / size_y

    current_fill_ratio = value / (total_gauge_values - 1.0) if total_gauge_values > 1 else 0.0

    # For rounded tips, we'll use FancyBboxPatch for continuous, or rely on D3.js's rounded rects for segments.
    # Matplotlib's Rectangle doesn't directly support rx/ry for rounded corners.
    # We'll simulate rounded ends for continuous using FancyBboxPatch, and for segments,
    # we'll use square ends in Matplotlib as it's simpler and D3.js handles rounded segments better.

    if orientation == "horizontal":
        bar_height_ratio = bar_thickness_ratio_y
        bar_width_ratio = 1 - 2 * padding_x_ratio
        bar_x = padding_x_ratio
        bar_y = 0.5 - bar_height_ratio / 2

        if num_segments > 1 and tip_style == "Straight": # Segmented horizontal (straight ends)
            total_drawable_length_pixels = size_x * bar_width_ratio
            total_gap_length_pixels = (num_segments - 1) * linear_segment_gap_pixels
            single_segment_length_pixels = (total_drawable_length_pixels - total_gap_length_pixels) / num_segments
            single_segment_length_ratio = single_segment_length_pixels / size_x

            current_pos_x = bar_x
            num_active_segments = int(round(current_fill_ratio * num_segments))

            for i in range(num_segments):
                color = active_color if i < num_active_segments else inactive_color
                ax.add_patch(Rectangle(
                    (current_pos_x, bar_y),
                    single_segment_length_ratio,
                    bar_height_ratio,
                    facecolor=color,
                    edgecolor='none',
                    linewidth=0,
                    transform=ax.transAxes
                ))
                current_pos_x += single_segment_length_ratio + (linear_segment_gap_pixels / size_x)
        else: # Continuous horizontal
            # Apply 3D effect for continuous linear gauges
            if is_3d:
                num_shadow_layers = 5
                offset_factor = 0.0005 * bar_height_ratio # Small offset relative to bar height

                active_rgb = to_rgb(active_color)
                inactive_rgb = to_rgb(inactive_color)

                for i in range(num_shadow_layers, -1, -1):
                    current_offset_x = i * offset_factor
                    current_offset_y = i * offset_factor

                    # Inactive shadow bar
                    ax.add_patch(Rectangle(
                        (bar_x + current_offset_x, bar_y - current_offset_y),
                        bar_width_ratio,
                        bar_height_ratio,
                        facecolor=tuple(c * (1 - 0.1 * i) for c in inactive_rgb),
                        edgecolor='none',
                        linewidth=0,
                        transform=ax.transAxes,
                        zorder=i
                    ))

                    # Active shadow bar
                    active_width_ratio = current_fill_ratio * bar_width_ratio
                    if value > 0 and active_width_ratio < (1 / size_x):
                        active_width_ratio = (1 / size_x) * 2
                    if active_width_ratio > 0:
                        ax.add_patch(Rectangle(
                            (bar_x + current_offset_x, bar_y - current_offset_y),
                            active_width_ratio,
                            bar_height_ratio,
                            facecolor=tuple(c * (1 - 0.1 * i) for c in active_rgb),
                            edgecolor='none',
                            linewidth=0,
                            transform=ax.transAxes,
                            zorder=i + 0.5
                        ))

            # Draw the main (front) inactive bar
            ax.add_patch(Rectangle(
                (bar_x, bar_y),
                bar_width_ratio,
                bar_height_ratio,
                facecolor=inactive_color,
                edgecolor='none',
                linewidth=0,
                transform=ax.transAxes,
                zorder=100
            ))
            # Draw the main (front) active bar
            active_width_ratio = current_fill_ratio * bar_width_ratio
            if value > 0 and active_width_ratio < (1 / size_x): # Ensure a minimum visible bar for value > 0
                active_width_ratio = (1 / size_x) * 2 # At least 2 pixels wide to be visible

            if active_width_ratio > 0:
                ax.add_patch(Rectangle(
                    (bar_x, bar_y),
                    active_width_ratio,
                    bar_height_ratio,
                    facecolor=active_color,
                    edgecolor='none',
                    linewidth=0,
                    transform=ax.transAxes,
                    zorder=101
                ))
    
        # Text positioning for horizontal
        if show_name and gauge_name:
            ax.text(0.5, bar_y - 0.05, gauge_name, ha='center', va='bottom', color=gauge_name_color, fontsize=bar_height_ratio * 1000, transform=ax.transAxes, zorder=120)
        if show_value:
            ax.text(bar_x + current_fill_ratio * bar_width_ratio, bar_y + bar_height_ratio + 0.05, f"{value}", ha='center', va='top', color=gauge_value_color, fontsize=bar_height_ratio * 1200, transform=ax.transAxes, zorder=120)

    else: # orientation == "vertical"
        bar_width_ratio = bar_thickness_ratio_x
        bar_height_ratio = 1 - 2 * padding_y_ratio
        bar_x = 0.5 - bar_width_ratio / 2
        bar_y = padding_y_ratio

        if num_segments > 1 and tip_style == "Straight": # Segmented vertical (straight ends)
            total_drawable_length_pixels = size_y * bar_height_ratio
            total_gap_length_pixels = (num_segments - 1) * linear_segment_gap_pixels
            single_segment_length_pixels = (total_drawable_length_pixels - total_gap_length_pixels) / num_segments
            single_segment_length_ratio = single_segment_length_pixels / size_y

            current_pos_y = bar_y
            num_active_segments = int(round(current_fill_ratio * num_segments))

            for i in range(num_segments):
                color = active_color if i < num_active_segments else inactive_color
                ax.add_patch(Rectangle(
                    (bar_x, current_pos_y),
                    bar_width_ratio,
                    single_segment_length_ratio,
                    facecolor=color,
                    edgecolor='none',
                    linewidth=0,
                    transform=ax.transAxes
                ))
                current_pos_y += single_segment_length_ratio + (linear_segment_gap_pixels / size_y)
        else: # Continuous vertical
            # Apply 3D effect for continuous linear gauges
            if is_3d:
                num_shadow_layers = 5
                offset_factor = 0.0005 * bar_width_ratio # Small offset relative to bar width

                active_rgb = to_rgb(active_color)
                inactive_rgb = to_rgb(inactive_color)

                for i in range(num_shadow_layers, -1, -1):
                    current_offset_x = i * offset_factor
                    current_offset_y = i * offset_factor

                    # Inactive shadow bar
                    ax.add_patch(Rectangle(
                        (bar_x + current_offset_x, bar_y + bar_height_ratio - (bar_height_ratio + current_offset_y)),
                        bar_width_ratio,
                        bar_height_ratio,
                        facecolor=tuple(c * (1 - 0.1 * i) for c in inactive_rgb),
                        edgecolor='none',
                        linewidth=0,
                        transform=ax.transAxes,
                        zorder=i
                    ))

                    # Active shadow bar
                    active_height_ratio = current_fill_ratio * bar_height_ratio
                    if value > 0 and active_height_ratio < (1 / size_y):
                        active_height_ratio = (1 / size_y) * 2
                    if active_height_ratio > 0:
                        ax.add_patch(Rectangle(
                            (bar_x + current_offset_x, bar_y + bar_height_ratio - active_height_ratio - current_offset_y),
                            bar_width_ratio,
                            active_height_ratio,
                            facecolor=tuple(c * (1 - 0.1 * i) for c in active_rgb),
                            edgecolor='none',
                            linewidth=0,
                            transform=ax.transAxes,
                            zorder=i + 0.5
                        ))

            # Draw inactive bar
            ax.add_patch(Rectangle(
                (bar_x, bar_y),
                bar_width_ratio,
                bar_height_ratio,
                facecolor=inactive_color,
                edgecolor='none',
                linewidth=0,
                transform=ax.transAxes,
                zorder=100
            ))
            # Draw active bar
            active_height_ratio = current_fill_ratio * bar_height_ratio
            if value > 0 and active_height_ratio < (1 / size_y): # Ensure a minimum visible bar for value > 0
                active_height_ratio = (1 / size_y) * 2 # At least 2 pixels high to be visible

            if active_height_ratio > 0:
                ax.add_patch(Rectangle(
                    (bar_x, bar_y + bar_height_ratio - active_height_ratio), # Draw from bottom up for vertical fill
                    bar_width_ratio,
                    active_height_ratio,
                    facecolor=active_color,
                    edgecolor='none',
                    linewidth=0,
                    transform=ax.transAxes,
                    zorder=101
                ))

        # Text positioning for vertical
        if show_name and gauge_name:
            ax.text(bar_x - 0.05, 0.5, gauge_name, ha='right', va='center', rotation=90, color=gauge_name_color, fontsize=bar_width_ratio * 1000, transform=ax.transAxes, zorder=120)
        if show_value:
            ax.text(bar_x + bar_width_ratio + 0.05, bar_y + bar_height_ratio - current_fill_ratio * bar_height_ratio, f"{value}", ha='left', va='center', color=gauge_value_color, fontsize=bar_width_ratio * 1200, transform=ax.transAxes, zorder=120)

    buf = io.BytesIO()
    plt.savefig(buf, format=image_format, bbox_inches='tight', pad_inches=0, transparent=False, dpi=output_dpi)
    plt.close(fig)
    buf.seek(0)
    return buf


# --- Streamlit Application Layout ---
import streamlit as st

# Page config
st.set_page_config(layout="centered", page_title="Gauge Image Generator and ICL Optimizer")

# Apply dark theme styles globally
bg_color_global = "#0E1117"
text_color = "#FFFFFF"

st.markdown(
    f"""
    <style>
    /* Main app background and text */
    .stApp {{ background-color: {bg_color_global}; color: {text_color}; }}
    /* Sidebar background and text */
    [data-testid="stSidebar"] {{ background-color: {bg_color_global}; color: {text_color}; }}
    /* Title headings */
    .css-1d391kg h1, .css-18ni7ap h1 {{ color: {text_color} !important; }}
    </style>
    """,
    unsafe_allow_html=True
)

# Title with dynamic text color
st.markdown(
    f"<h1 style='text-align:center; color:{text_color};'>Custom Gauge Image Generator and ICL Optimizer</h1>",
    unsafe_allow_html=True
)

# Sidebar for gauge parameters
with st.sidebar:
    st.header("Gauge Parameters")

    # Initialize defaults
    defaults = {
        'gauge_type': "Round",
        'output_width': 200,
        'output_height': 200,
        'gauge_value': 0,
        'active_color': "#1f77b4",
        'inactive_color': "#ff0000",
        'bg_color': "#000000",
        'gauge_thickness': 0.15,
        'start_angle': 175,
        'end_angle': 175,
        'fill_direction': "counter-clockwise",
        'num_segments': 50,
        'segment_gap_deg': 2.0,
        'linear_thickness': 30,
        'linear_orientation': "horizontal",
        'linear_num_segments': 50,
        'linear_segment_gap_pixels': 2,
        'tip_style': "Rounded",  # Tip style default
        'show_angle_markers': True,
        'show_value': True,
        'show_name': False,
        'gauge_name': "",
        'is_3d': True,
        'gauge_value_color': "#FFFFFF",
        'gauge_name_color': "#FFFFFF"
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # Live preview value slider (always visible)
    st.session_state['gauge_value'] = st.slider(
        "Gauge Value (for live preview)", 0, 99,
        value=st.session_state['gauge_value'], key="gauge_value_slider"
    )

    # Gauge type selector
    st.session_state['gauge_type'] = st.radio(
        "Select Gauge Type",
        ("Round", "Round Segmented", "Linear", "Linear Segmented"),
        index=["Round", "Round Segmented", "Linear", "Linear Segmented"].index(
            st.session_state['gauge_type']
        ), key="gauge_type_radio"
    )

    # Size inputs
    st.session_state['output_width'] = st.number_input(
        "Output Width (px)", 100, 1000,
        value=st.session_state['output_width'], step=10, key="width_input"
    )
    st.session_state['output_height'] = st.number_input(
        "Output Height (px)", 100, 1000,
        value=st.session_state['output_height'], step=10, key="height_input"
    )

    # Colors and 3D effect toggle
    st.session_state['active_color'] = st.color_picker(
        "Active Color", st.session_state['active_color'], key="active_color_picker"
    )
    st.session_state['inactive_color'] = st.color_picker(
        "Inactive Color", st.session_state['inactive_color'], key="inactive_color_picker"
    )
    st.session_state['bg_color'] = st.color_picker(
        "Background Color", st.session_state['bg_color'], key="bg_color_picker"
    )
    st.session_state['is_3d'] = st.checkbox(
        "Enable 3D Effect", value=st.session_state['is_3d'], key="is_3d_checkbox"
    )

    # Specific gauge settings
    if st.session_state['gauge_type'] in ["Round", "Round Segmented"]:
        st.session_state['gauge_thickness'] = st.slider(
            "Gauge Thickness (Relative)", 0.05, 0.3,
            value=st.session_state['gauge_thickness'], step=0.01,
            key="thickness_slider"
        )
        st.session_state['start_angle'] = st.number_input(
            "Start Angle (degrees)", 0, 360,
            value=st.session_state['start_angle'], step=5,
            key="start_angle_input"
        )
        st.session_state['end_angle'] = st.number_input(
            "End Angle (degrees)", 0, 360,
            value=st.session_state['end_angle'], step=5,
            key="end_angle_input"
        )
        st.session_state['fill_direction'] = st.radio(
            "Fill Direction", ("clockwise", "counter-clockwise"),
            index=["clockwise", "counter-clockwise"].index(
                st.session_state['fill_direction']
            ), key="fill_direction_radio"
        )
        st.session_state['show_angle_markers'] = st.checkbox(
            "Show Debug Angle Markers (0, 90, 180, 270)",
            value=st.session_state['show_angle_markers'], key="show_angle_markers_checkbox"
        )
        # Tip style selector (round vs straight ends)
        st.session_state['tip_style'] = st.radio(
            "Gauge Tip Style", ("Rounded", "Straight"),
            index=["Rounded", "Straight"].index(
                st.session_state['tip_style']
            ), key="tip_style_radio"
        )
        if st.session_state['gauge_type'] == "Round Segmented":
            st.session_state['num_segments'] = st.number_input(
                "Number of Segments", 1, 200,
                value=st.session_state['num_segments'], step=5,
                key="num_segments_input"
            )
            st.session_state['segment_gap_deg'] = st.slider(
                "Gap Between Segments (degrees)", 0.0, 10.0,
                value=st.session_state['segment_gap_deg'], step=0.5,
                key="segment_gap_deg_slider"
            )
        else:
            st.session_state['num_segments'] = 50
            st.session_state['segment_gap_deg'] = 0.0
    else:
        st.session_state['linear_thickness'] = st.slider(
            "Linear Gauge Thickness (px)", 10, 100,
            value=st.session_state['linear_thickness'], step=5,
            key="linear_thickness_slider"
        )
        st.session_state['linear_orientation'] = st.radio(
            "Linear Gauge Orientation", ("horizontal", "vertical"),
            index=["horizontal", "vertical"].index(
                st.session_state['linear_orientation']
            ), key="linear_orientation_radio"
        )
        # Tip style selector for linear gauges
        st.session_state['tip_style'] = st.radio(
            "Gauge Tip Style", ("Rounded", "Straight"),
            index=["Rounded", "Straight"].index(
                st.session_state['tip_style']
            ), key="tip_style_radio"
        )
        if st.session_state['gauge_type'] == "Linear Segmented":
            st.session_state['linear_num_segments'] = st.number_input(
                "Number of Segments", 1, 200,
                value=st.session_state['linear_num_segments'], step=5,
                key="linear_num_segments_input"
            )
            st.session_state['linear_segment_gap_pixels'] = st.slider(
                "Gap Between Segments (px)", 0, 20,
                value=st.session_state['linear_segment_gap_pixels'], step=1,
                key="linear_segment_gap_pixels_slider"
            )
        else:
            st.session_state['linear_num_segments'] = 50
            st.session_state['linear_segment_gap_pixels'] = 0

    # Determine if current gauge is linear type
    is_linear = st.session_state['gauge_type'] in ["Linear", "Linear Segmented"]

    # Show Gauge Value checkbox
    sv = st.checkbox(
        "Show Gauge Value on Chart",
        value=False if is_linear else st.session_state.get('show_value', True),
        disabled=is_linear,
        key="show_value_checkbox"
    )
    st.session_state['show_value'] = False if is_linear else sv
    if st.session_state['show_value']:
        st.session_state['gauge_value_color'] = st.color_picker(
            "Gauge Value Color", st.session_state['gauge_value_color'],
            key="gauge_value_color_picker"
        )

    # Show Gauge Name checkbox
    sn = st.checkbox(
        "Show Gauge Name on Chart",
        value=False if is_linear else st.session_state.get('show_name', False),
        disabled=is_linear,
        key="show_name_checkbox"
    )
    st.session_state['show_name'] = False if is_linear else sn
    if st.session_state['show_name']:
        st.session_state['gauge_name'] = st.text_input(
            "Gauge Name (optional)", st.session_state['gauge_name'],
            key="gauge_name_input"
        )
        st.session_state['gauge_name_color'] = st.color_picker(
            "Gauge Name Color", st.session_state['gauge_name_color'],
            key="gauge_name_color_picker"
        )
    else:
        st.session_state['gauge_name'] = ""






# Main content area
st.write("Use the main area below to see the live preview and download options.")

tab_titles = ["Gauge Generator", "ICL Optimizer"]
selected_tab_title_obj = st.tabs(tab_titles)

with selected_tab_title_obj[0]: # Gauge Generator Tab
    st.markdown(
    "<h2 style='color:white; margin-bottom: 0.5rem;'>Live Gauge Preview</h2>",
    unsafe_allow_html=True,
    )
    st.info("The live preview below is for interactive rendering. Use the sidebar to adjust parameters.")

    component_width_for_iframe = st.session_state['output_width']
    component_height_for_iframe = st.session_state['output_height']

    # D3.js HTML content
    d3_html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Gauge Preview</title>
        <script src="https://d3js.org/d3.v7.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
        <style>
            body {{margin: 0; overflow: hidden; background-color: {st.session_state['bg_color']};}}
            svg {{display: block;}}
            .gauge-value-text {{
                font-family: sans-serif;
                font-size: 40px; /* Fixed size for reliability */
                font-weight: bold;
                text-anchor: middle;
                fill: {st.session_state['gauge_value_color']};
            }}
            .gauge-name-text {{
                font-family: sans-serif;
                font-size: 30px; /* Fixed size for reliability */
                font-weight: bold;
                text-anchor: middle;
                fill: {st.session_state['gauge_name_color']};
            }}
            .angle-marker-text {{
                font-family: sans-serif;
                font-size: 12px;
                fill: #ddd;
                text-anchor: middle;
                dominant-baseline: central;
            }}
        </style>
    </head>
    <body>
        <div id="gauge-container" style="width: {{width}}px; height: {{height}}px; margin: 0 auto;"></div>
        <div id="d3-status-message" style="text-align: center; margin-top: 10px; font-weight: bold; color: #333;"></div>
        <script>
            // saveSvgAsPng.js functionality (embedded directly)
            // Original source: https://github.com/exupero/saveSvgAsPng/blob/gh-pages/saveSvgAsPng.js
            // Version 1.4.17
            (function() {{
                var out$ = typeof exports != 'undefined' && exports || this;

                var defaultOpts = {{
                    scale: 1,
                    canvg: './canvg.js',
                    encoderOptions: 0.8,
                    backgroundColor: 'white',
                    excludeUnusedCss: true,
                    width: null,
                    height: null,
                    left: 0,
                    top: 0,
                    force: 'no'
                }};

                out$.svgAsPngUri = function(el, options, cb) {{
                    options = Object.assign({{}}, defaultOpts, options);
                    var svg = el.cloneNode(true);
                    svg.style.backgroundColor = options.backgroundColor;

                    var canvas = document.createElement('canvas');
                    var ctx = canvas.getContext('2d');

                    var svgRect = el.getBoundingClientRect();
                    var width = options.width || svgRect.width;
                    var height = options.height || svgRect.height;
                    var left = options.left || svgRect.left;
                    var top = options.top || svgRect.top;

                    // Ensure minimum dimensions
                    width = Math.max(1, width);
                    height = Math.max(1, height);

                    canvas.width = Math.max(1, width * options.scale);
                    canvas.height = Math.max(1, height * options.scale);
                    canvas.style.width = width + 'px';
                    canvas.style.height = height + 'px';

                    ctx.scale(options.scale, options.scale);

                    var DOMURL = window.URL || window.webkitURL || window;
                    var img = new Image();
                    var svgStr = new XMLSerializer().serializeToString(svg);
                    var blob = new Blob([svgStr], {{type: 'image/svg+xml;charset=utf-8'}});
                    var url = DOMURL.createObjectURL(blob);

                    img.onload = function() {{
                        ctx.drawImage(img, left, top, width, height, 0, 0, width, height);
                        DOMURL.revokeObjectURL(url);
                        var uri = canvas.toDataURL('image/png', options.encoderOptions);
                        cb(uri);
                    }};
                    img.onerror = function(err) {{
                        console.error("Error loading SVG into image for conversion:", err);
                        cb(null); // Indicate failure
                    }};
                    img.src = url;
                }};
            }})();
            // End of saveSvgAsPng.js functionality

            const container = d3.select("#gauge-container");
            const width = {st.session_state['output_width']};
            const height = {st.session_state['output_height']};
            const centerX = width / 2;
            const centerY = height / 2;

            const livePreviewValue = {st.session_state['gauge_value']};
            const totalValues = 100;
            
            const activeColor = '{st.session_state['active_color']}';
            const inactiveColor = '{st.session_state['inactive_color']}';
            const showValue = {str(st.session_state['show_value']).lower()};
            const showName = {str(st.session_state['show_name']).lower()};
            const gaugeName = "{st.session_state['gauge_name']}";
            const backgroundColor = "{st.session_state['bg_color']}";
            const showAngleMarkers = {str(st.session_state['show_angle_markers']).lower()};
            const gaugeType = "{st.session_state['gauge_type']}";
            const tipStyle = "{st.session_state['tip_style']}";
            const gaugeValueColor = "{st.session_state['gauge_value_color']}"; // Pass to JS
            const gaugeNameColor = "{st.session_state['gauge_name_color']}"; // Pass to JS


            const roundGaugeThickness = {st.session_state['gauge_thickness']};
            const roundStartAngleDeg = {st.session_state['start_angle']};
            const roundEndAngleDeg = {st.session_state['end_angle']};
            const roundFillDirection = '{st.session_state['fill_direction']}';
            const roundNumSegments = {st.session_state['num_segments']};
            const roundSegmentGapDeg = {st.session_state['segment_gap_deg']};

            const linearThickness = {st.session_state['linear_thickness']};
            const linearOrientation = '{st.session_state['linear_orientation']}';
            const linearNumSegments = {st.session_state['linear_num_segments']};
            const linearSegmentGapPixels = {st.session_state['linear_segment_gap_pixels']};


            const EPSILON = 0.0001;

            function degToRad(degrees) {{
                return degrees * Math.PI / 180;
            }}

            // Function to create radial gradients with more pronounced 3D effect
            function createRadialGradient(defs, id, baseColor) {{
                const r = d3.color(baseColor).rgb();
                const lightColor = `rgb(${{Math.min(255, r.r + 100)}}, ${{Math.min(255, r.g + 100)}}, ${{Math.min(255, r.b + 100)}})`;
                const midColor = `rgb(${{r.r}}, ${{r.g}}, ${{r.b}})`;
                const darkColor = `rgb(${{Math.max(0, r.r - 100)}}, ${{Math.max(0, r.g - 100)}}, ${{Math.max(0, r.b - 100)}})`;

                defs.append("radialGradient")
                    .attr("id", id)
                    .attr("cx", "50%") .attr("cy", "50%")
                    .attr("r", "70%")
                    .attr("fx", "35%") .attr("fy", "35%")
                    .selectAll("stop")
                    .data([
                        {{offset: "0%", color: lightColor}},
                        {{offset: "50%", color: midColor}},
                        {{offset: "100%", color: darkColor}}
                    ])
                    .enter().append("stop")
                    .attr("offset", d => d.offset)
                    .attr("stop-color", d => d.color);
            }}

            // Function to create linear gradients (for linear gauges)
            function createLinearGradient(defs, id, baseColor, orientation) {{
                const r = d3.color(baseColor).rgb();
                const lightColor = `rgb(${{Math.min(255, r.r + 100)}}, ${{Math.min(255, r.g + 100)}}, ${{Math.min(255, r.b + 100)}})`;
                const midColor = `rgb(${{r.r}}, ${{r.g}}, ${{r.b}})`;
                const darkColor = `rgb(${{Math.max(0, r.r - 100)}}, ${{Math.max(0, r.g - 100)}}, ${{Math.max(0, r.b - 100)}})`;

                const gradient = defs.append("linearGradient").attr("id", id);

                if (orientation === "horizontal") {{
                    gradient.attr("x1", "0%").attr("y1", "0%").attr("x2", "0%").attr("y2", "100%");
                }} else {{ // vertical
                    gradient.attr("x1", "0%").attr("y1", "0%").attr("x2", "100%").attr("y2", "0%");
                }}

                gradient.append("stop").attr("offset", "0%").attr("stop-color", lightColor);
                gradient.append("stop").attr("offset", "50%").attr("stop-color", midColor);
                gradient.append("stop").attr("offset", "100%").attr("stop-color", darkColor);
            }}

            function drawGauge(svgContext, currentValue, gaugeType) {{
                svgContext.selectAll("g").remove(); // Clear previous gauge elements

                const g = svgContext.append("g")
                    .attr("transform", `translate(${{centerX}}, ${{centerY}})`);

                // Define gradients once
                if (svgContext.select("defs").empty()) {{
                    const defs = svgContext.append("defs");
                    createRadialGradient(defs, "activeRadialGradient", activeColor);
                    createRadialGradient(defs, "inactiveRadialGradient", inactiveColor);
                    createLinearGradient(defs, "activeLinearGradient", activeColor, linearOrientation);
                    createLinearGradient(defs, "inactiveLinearGradient", inactiveColor, linearOrientation);
                }}

                const currentFillRatio = Math.min(1, currentValue / totalValues);

                if (gaugeType === "Round" || gaugeType === "Round Segmented") {{
                    const outerRadius = Math.min(width, height) / 2 * 0.9;
                    const innerRadius = outerRadius * (1 - roundGaugeThickness);
                    const markerRadius = outerRadius * 0.8;
                    
                    // Dynamic font sizes based on outerRadius for better scaling
                    const valueFontSize = outerRadius * 0.45; 
                    const nameFontSize = outerRadius * 0.3;

                    let rawStartRad = degToRad(roundStartAngleDeg);
                    let rawEndRad = degToRad(roundEndAngleDeg);

                    let totalSweepMagnitude;
                    if (roundFillDirection === "counter-clockwise") {{
                        totalSweepMagnitude = rawEndRad - rawStartRad;
                        if (totalSweepMagnitude < -EPSILON) totalSweepMagnitude += 2 * Math.PI;
                        else if (totalSweepMagnitude > 2 * Math.PI + EPSILON) totalSweepMagnitude -= 2 * Math.PI;
                    }} else {{ // clockwise
                        totalSweepMagnitude = rawStartRad - rawEndRad;
                        if (totalSweepMagnitude < -EPSILON) totalSweepMagnitude += 2 * Math.PI;
                        else if (totalSweepMagnitude > 2 * Math.PI + EPSILON) totalSweepMagnitude -= 2 * Math.PI;
                    }}
                    
                    if (Math.abs(totalSweepMagnitude) < EPSILON && Math.abs(rawStartRad - rawEndRad) < EPSILON) {{
                        totalSweepMagnitude = 2 * Math.PI; // Full circle if start and end are same
                    }}

                    const arcGenerator = d3.arc()
                        .innerRadius(innerRadius)
                        .outerRadius(outerRadius)
                        .cornerRadius(tipStyle === "Rounded" ? (outerRadius - innerRadius) / 2 : 0);

                    if (gaugeType === "Round") {{ // Continuous Round
                        let filledSweepMagnitude;
                        const minActiveAngle = degToRad(2); // Minimum angle for value 1 to be visible

                        if (currentValue === 0) {{
                            filledSweepMagnitude = 0;
                        }} else if (currentValue === 1 && totalSweepMagnitude > 0) {{
                            filledSweepMagnitude = minActiveAngle; // Show a sliver for value 1
                        }} else {{
                            filledSweepMagnitude = currentFillRatio * totalSweepMagnitude;
                        }}

                        let baseArcEnd;
                        if (roundFillDirection === "counter-clockwise") {{
                            baseArcEnd = rawStartRad + totalSweepMagnitude;
                        }} else {{
                            baseArcEnd = rawStartRad - totalSweepMagnitude;
                        }}

                        g.append("path")
                            .attr("d", arcGenerator({{startAngle: rawStartRad, endAngle: baseArcEnd}}))
                            .attr("fill", "url(#inactiveRadialGradient)");

                        if (filledSweepMagnitude > 0) {{
                            let activeArcEnd;
                            if (roundFillDirection === "counter-clockwise") {{
                                activeArcEnd = rawStartRad + filledSweepMagnitude;
                            }} else {{
                                activeArcEnd = rawStartRad - filledSweepMagnitude;
                            }}
                            
                            g.append("path")
                                .attr("d", arcGenerator({{startAngle: rawStartRad, endAngle: activeArcEnd}}))
                                .attr("fill", "url(#activeRadialGradient)");
                        }}

                    }} else if (gaugeType === "Round Segmented") {{
                        const totalEffectiveSweep = totalSweepMagnitude - (roundNumSegments * degToRad(roundSegmentGapDeg));
                        const singleSegmentAngle = totalEffectiveSweep / roundNumSegments;

                        let currentSegmentStartAngle = rawStartRad;
                        const numActiveSegments = Math.floor(currentFillRatio * roundNumSegments);

                        for (let i = 0; i < roundNumSegments; i++) {{
                            const segmentColor = i < numActiveSegments ? "url(#activeRadialGradient)" : "url(#inactiveRadialGradient)";
                            
                            let theta1_segment, theta2_segment;
                            if (roundFillDirection === "counter-clockwise") {{
                                theta1_segment = currentSegmentStartAngle;
                                theta2_segment = currentSegmentStartAngle + singleSegmentAngle;
                            }} else {{
                                theta1_segment = currentSegmentStartAngle - singleSegmentAngle;
                                theta2_segment = currentSegmentStartAngle;
                            }}

                            g.append("path")
                                .attr("d", arcGenerator({{startAngle: theta1_segment, endAngle: theta2_segment}}))
                                .attr("fill", segmentColor);

                            if (roundFillDirection === "counter-clockwise") {{
                                currentSegmentStartAngle += (singleSegmentAngle + degToRad(roundSegmentGapDeg));
                            }} else {{
                                currentSegmentStartAngle -= (singleSegmentAngle + degToRad(roundSegmentGapDeg));
                            }}
                        }}
                    }}

                    if (showAngleMarkers) {{
                        const angles = [0, 90, 180, 270];
                        angles.forEach(angleDeg => {{
                            const angleRad = degToRad(angleDeg);
                            const x = markerRadius * Math.cos(angleRad);
                            const y = markerRadius * Math.sin(angleRad);
                            
                            g.append("circle")
                                .attr("cx", x)
                                .attr("cy", y)
                                .attr("r", 3)
                                .attr("fill", "red");
                            
                            let textOffsetX = 0;
                            let textOffsetY = 0;
                            const textOffsetDistance = outerRadius * 0.15;
                            let textAnchor = "middle";
                            
                            if (angleDeg === 0) {{
                                textOffsetX = textOffsetDistance;
                                textAnchor = "start";
                            }} else if (angleDeg === 90) {{
                                textOffsetY = -textOffsetDistance;
                                textAnchor = "middle";
                            }} else if (angleDeg === 180) {{
                                textOffsetX = -textOffsetDistance;
                                textAnchor = "end";
                            }} else if (angleDeg === 270) {{
                                textOffsetY = textOffsetDistance;
                                textAnchor = "middle";
                            }}

                            g.append("text")
                                .attr("class", "angle-marker-text")
                                .attr("x", x + textOffsetX)
                                .attr("y", y + textOffsetY)
                                .attr("text-anchor", textAnchor)
                                .text(angleDeg + "°");
                        }});
                    }}

                    // Determine text Y positions based on whether both are shown
                    let valueTextY = 0;
                    let nameTextY = 0;

                    if (showValue && showName) {{
                        valueTextY = -20; // Value 20px above center
                        nameTextY = 20; // Name 20px below center
                    }} else if (showValue && !showName) {{
                        valueTextY = 0; // Value centered if no name
                    }} else if (!showValue && showName) {{
                        nameTextY = 0; // Name centered if no value
                    }}

                    // Add Gauge Name text if requested
                    if (showName && gaugeName) {{
                        g.append("text")
                            .attr("x", 0)
                            .attr("y", nameTextY)
                            .attr("fill", gaugeNameColor)
                            .attr("font-family", "sans-serif")
                            .attr("font-size", "30px")
                            .attr("font-weight", "bold")
                            .attr("text-anchor", "middle")
                            .attr("dominant-baseline", "central")
                            .text(gaugeName);
                    }}

                    // Add Gauge Value text if requested
                    if (showValue) {{
                        g.append("text")
                            .attr("x", 0)
                            .attr("y", valueTextY)
                            .attr("fill", gaugeValueColor)
                            .attr("font-family", "sans-serif")
                            .attr("font-size", "40px")
                            .attr("font-weight", "bold")
                            .attr("text-anchor", "middle")
                            .attr("dominant-baseline", "central")
                            .text(currentValue);
                    }}
                }} else if (gaugeType === "Linear" || gaugeType === "Linear Segmented") {{
                    const padding = 20;
                    let xStart, yStart, xEnd, yEnd;
                    const currentRx = tipStyle === "Rounded" ? linearThickness / 2 : 0;
                    const currentRy = tipStyle === "Rounded" ? linearThickness / 2 : 0;

                    if (linearOrientation === "horizontal") {{
                        xStart = -width / 2 + padding;
                        yStart = -linearThickness / 2;
                        xEnd = width / 2 - padding;
                        yEnd = linearThickness / 2;

                        if (gaugeType === "Linear") {{ // Continuous Linear
                            g.append("rect")
                                .attr("x", xStart)
                                .attr("y", yStart)
                                .attr("width", xEnd - xStart)
                                .attr("height", linearThickness)
                                .attr("rx", currentRx)
                                .attr("ry", currentRy)
                                .attr("fill", "url(#inactiveLinearGradient)");

                            let activeWidth = currentFillRatio * (xEnd - xStart);
                            activeWidth = Math.max(0, Math.min(xEnd - xStart, activeWidth));
                            if (currentValue > 0 && activeWidth < 1) activeWidth = 1; // Ensure a minimum visible bar for value > 0

                            if (currentValue > 0) {{
                                g.append("rect")
                                    .attr("x", xStart)
                                    .attr("y", yStart)
                                    .attr("width", activeWidth)
                                    .attr("height", linearThickness)
                                    .attr("rx", tipStyle === "Rounded" ? Math.min(linearThickness / 2, activeWidth / 2) : 0)
                                    .attr("ry", currentRy)
                                    .attr("fill", "url(#activeLinearGradient)");
                            }}
                        }} else {{ // Linear Segmented
                            const totalBarLength = width - 2 * padding;
                            const totalGapLength = linearNumSegments > 1 ? (linearNumSegments - 1) * linearSegmentGapPixels : 0;
                            let segmentLength = (totalBarLength - totalGapLength) / linearNumSegments;
                            if (segmentLength < 0) segmentLength = 0;

                            let currentPosition = -width / 2 + padding;

                            for (let i = 0; i < linearNumSegments; i++) {{
                                const segmentColor = i < (currentFillRatio * linearNumSegments) ? "url(#activeLinearGradient)" : "url(#inactiveLinearGradient)";
                                
                                g.append("rect")
                                    .attr("x", currentPosition)
                                    .attr("y", -linearThickness / 2)
                                    .attr("width", segmentLength)
                                    .attr("height", linearThickness)
                                    .attr("rx", currentRx)
                                    .attr("ry", currentRy)
                                    .attr("fill", segmentColor);
                                
                                currentPosition += segmentLength + linearSegmentGapPixels;
                            }}
                        }}

                        if (showName && gaugeName) {{
                            g.append("text")
                                .attr("class", "gauge-name-text")
                                .attr("x", 0)
                                .attr("y", -linearThickness / 2 - 20)
                                .attr("fill", gaugeNameColor)
                                .text(gaugeName);
                        }}
                        if (showValue) {{
                            let valueTextX;
                            if (gaugeType === "Linear") {{
                                if (currentValue === 0) {{
                                    valueTextX = xStart;
                                }} else if (currentValue === totalValues) {{
                                    valueTextX = xEnd;
                                }} else {{
                                    valueTextX = xStart + currentFillRatio * (xEnd - xStart);
                                }}
                            }} else {{ // Segmented, value text centered
                                valueTextX = 0;
                            }}
                            
                            g.append("text")
                                .attr("class", "gauge-value-text")
                                .attr("x", valueTextX)
                                .attr("y", linearThickness / 2 + 30)
                                .attr("fill", gaugeValueColor)
                                .text(currentValue);
                        }}

                    }} else {{ // vertical
                        xStart = -linearThickness / 2;
                        yStart = height / 2 - padding; // Top of the bar
                        xEnd = linearThickness / 2;
                        yEnd = -height / 2 + padding; // Bottom of the bar

                        if (gaugeType === "Linear") {{ // Continuous Linear
                            g.append("rect")
                                .attr("x", xStart)
                                .attr("y", yEnd) // Draw from bottom up
                                .attr("width", linearThickness)
                                .attr("height", yStart - yEnd)
                                .attr("rx", currentRx)
                                .attr("ry", currentRy)
                                .attr("fill", "url(#inactiveLinearGradient)");

                            let activeHeight = currentFillRatio * (yStart - yEnd);
                            activeHeight = Math.max(0, Math.min(yStart - yEnd, activeHeight));
                            if (currentValue > 0 && activeHeight < 1) activeHeight = 1; // Ensure minimum visible bar

                            if (currentValue > 0) {{
                                g.append("rect")
                                    .attr("x", xStart)
                                    .attr("y", yStart - activeHeight) // Draw from bottom up
                                    .attr("width", linearThickness)
                                    .attr("height", activeHeight)
                                    .attr("rx", currentRx)
                                    .attr("ry", tipStyle === "Rounded" ? Math.min(linearThickness / 2, activeHeight / 2) : 0)
                                    .attr("fill", "url(#activeLinearGradient)");
                            }}
                        }} else {{ // Linear Segmented
                            const totalBarLength = height - 2 * padding;
                            const totalGapLength = linearNumSegments > 1 ? (linearNumSegments - 1) * linearSegmentGapPixels : 0;
                            let segmentLength = (totalBarLength - totalGapLength) / linearNumSegments;
                            if (segmentLength < 0) segmentLength = 0;

                            let currentPosition = height / 2 - padding; // Start from top for vertical segments

                            for (let i = 0; i < linearNumSegments; i++) {{
                                const segmentColor = i < (currentFillRatio * linearNumSegments) ? "url(#activeLinearGradient)" : "url(#inactiveLinearGradient)";
                                
                                g.append("rect")
                                    .attr("x", -linearThickness / 2)
                                    .attr("y", currentPosition - segmentLength) // Draw segments downwards
                                    .attr("width", linearThickness)
                                    .attr("height", segmentLength)
                                    .attr("rx", currentRx)
                                    .attr("ry", currentRy)
                                    .attr("fill", segmentColor);
                                
                                currentPosition -= (segmentLength + linearSegmentGapPixels);
                            }}
                        }}

                        if (showName && gaugeName) {{
                            g.append("text")
                                .attr("class", "gauge-name-text")
                                .attr("x", linearThickness / 2 + 20)
                                .attr("y", 0)
                                .attr("text-anchor", "start")
                                .attr("fill", gaugeNameColor)
                                .text(gaugeName);
                        }}
                        if (showValue) {{
                            let valueTextY;
                            if (gaugeType === "Linear") {{
                                if (currentValue === 0) {{
                                    valueTextY = yStart;
                                }} else if (currentValue === totalValues) {{
                                    valueTextY = yEnd;
                                }} else {{
                                    valueTextY = yStart - currentFillRatio * (yStart - yEnd);
                                }}
                            }} else {{ // Segmented, value text centered
                                valueTextY = 0;
                            }}
                            g.append("text")
                                .attr("class", "gauge-value-text")
                                .attr("x", -linearThickness / 2 - 30)
                                .attr("y", valueTextY)
                                .attr("text-anchor", "end")
                                .attr("fill", gaugeValueColor)
                                .text(currentValue);
                        }}
                    }}
                }}
            }}

            // Function to download SVG as PNG (using the embedded functionality)
            function downloadSVGAsPNG(svgElement, filename, value) {{
                svgAsPngUri(svgElement, {{width: width, height: height, backgroundColor: backgroundColor}}, function(uri) {{
                    if (uri) {{
                        const downloadLink = document.createElement("a");
                        downloadLink.href = uri;
                        downloadLink.download = `gauge_${{value}}.png`;
                        document.body.appendChild(downloadLink);
                        downloadLink.click();
                        document.body.removeChild(downloadLink);
                    }} else {{
                        console.error("Failed to generate PNG URI for single gauge.");
                    }}
                }});
            }}

            // Function to download all 100 D3.js gauges
            async function downloadAllGauges() {{
                const statusMessageDiv = document.getElementById('d3-status-message');
                statusMessageDiv.style.color = '#007bff';
                statusMessageDiv.innerText = 'Generating gauges (0/99)... Please wait.';
                console.log("Starting bulk gauge generation...");

                const zip = new JSZip();
                const totalGauges = 100;
                const gaugeTypeForFilename = gaugeType.toLowerCase().replace(' ', '_');

                const tempSvg = d3.create("svg")
                    .attr("width", width)
                    .attr("height", height)
                    .attr("viewBox", `0 0 ${{width}} ${{height}}`)
                    .style("background-color", backgroundColor);

                const defs = tempSvg.append("defs");
                createRadialGradient(defs, "activeRadialGradient", activeColor);
                createRadialGradient(defs, "inactiveRadialGradient", inactiveColor);
                createLinearGradient(defs, "activeLinearGradient", activeColor, linearOrientation);
                createLinearGradient(defs, "inactiveLinearGradient", inactiveColor, linearOrientation);

                // Ensure svgAsPngUri is available (it should be now that it's embedded)
                if (typeof svgAsPngUri === 'undefined') {{
                    statusMessageDiv.style.color = 'red';
                    statusMessageDiv.innerText = 'Error: svgAsPngUri function not found. Image generation aborted.';
                    console.error('svgAsPngUri function is not defined, despite embedding attempt.');
                    return;
                }}

                try {{
                    for (let i = 0; i < totalGauges; i++) {{
                        statusMessageDiv.innerText = `Generating gauges (${{i + 1}}/{{totalGauges}})...`;
                        console.log(`Attempting to generate gauge for value ${{i}}`);

                        tempSvg.selectAll("g").remove(); // Clear previous content
                        drawGauge(tempSvg, i, gaugeType); // Draw the current gauge

                        // Add a small delay to allow SVG rendering to settle
                        await new Promise(resolve => setTimeout(resolve, 50));

                        let dataUri;
                        try {{
                            dataUri = await new Promise((resolve) => {{
                                svgAsPngUri(tempSvg.node(), {{scale: 1, encoderOptions: 1, width: width, height: height, backgroundColor: backgroundColor}}, resolve);
                            }});
                            console.log(`Data URI for value ${{i}}:`, dataUri); // Added log for debugging
                            if (!dataUri) {{
                                throw new Error("svgAsPngUri returned empty data URI.");
                            }}
                        }} catch (svgError) {{
                            console.error(`Error converting SVG to PNG for value ${{i}}:`, svgError);
                            statusMessageDiv.style.color = 'red';
                            statusMessageDiv.innerText = `Error converting gauge ${{i}} to PNG. Check console.`;
                            return; // Stop execution on critical error
                        }}
                        
                        const base64Data = dataUri.split(',')[1];
                        if (!base64Data) {{
                            console.error(`Base64 data missing for value ${{i}} from URI: ${{dataUri}}`);
                            statusMessageDiv.style.color = 'red';
                            statusMessageDiv.innerText = `Error processing base64 data for gauge ${{i}}. Check console.`;
                            return; // Stop execution
                        }}
                        zip.file(`${{i.toString().padStart(2, '0')}}_${{gaugeTypeForFilename}}.png`, base64Data, {{base64: true}});
                        
                        // Yield control to the browser (already present, but good to keep)
                        await new Promise(resolve => setTimeout(resolve, 10)); 
                    }}

                    statusMessageDiv.innerText = 'Zipping all D3.js gauges... This may take a moment.';
                    console.log("Starting D3.js zip generation...");
                    zip.generateAsync({{type:"blob", compression: "DEFLATE", compressionOptions: {{level: 9}}}})
                        .then(function(content) {{
                            const downloadLink = document.createElement("a");
                            downloadLink.href = URL.createObjectURL(content);
                            downloadLink.download = "all_gauges.zip";
                            document.body.appendChild(downloadLink);
                            downloadLink.click();
                            document.body.removeChild(downloadLink);
                            statusMessageDiv.style.color = '#28a745';
                            statusMessageDiv.innerText = 'All gauges generated and download started!';
                            console.log("gauges zip generated and download initiated.");
                        }})
                        .catch(function(error) {{
                            statusMessageDiv.style.color = 'red';
                            statusMessageDiv.innerText = 'Error zipping gauges. Check console.';
                            console.error("Error generating zip:", error);
                        }});
                }} catch (error) {{
                    statusMessageDiv.style.color = 'red';
                    statusMessageDiv.innerText = 'An unexpected error occurred during gauge generation. Check console.';
                    console.error("Unexpected error in downloadAllGauges:", error);
                }}
            }}

            const liveSvg = container.append("svg")
                .attr("width", width)
                .attr("height", height)
                .attr("viewBox", `0 0 ${{width}} ${{height}}`)
                .style("background-color", backgroundColor);
            drawGauge(liveSvg, livePreviewValue, gaugeType);

            // Add download button functionality for single image
            window.downloadCurrentGauge = function() {{
                downloadSVGAsPNG(liveSvg.node(), `gauge_${{livePreviewValue}}.png`, livePreviewValue);
            }};

            // Expose the bulk download function to the global scope
            window.downloadAllGauges = downloadAllGauges;
        </script>
        <div style="text-align: center; margin-top: 20px;">
            <button onclick="window.downloadCurrentGauge()" style="padding: 10px 20px; font-size: 16px; background-color: #007bff; color: white; border: none; border-radius: 8px; cursor: pointer; margin-bottom: 10px;">
                Download Current Gauge
            </button>
            <button onclick="window.downloadAllGauges()" style="padding: 10px 20px; font-size: 16px; background-color: #28a745; color: white; border: none; border-radius: 8px; cursor: pointer;">
                Generate and Download All Gauges (0-99)
            </button>
        </div>
    </body>
    </html>
    """
    st.components.v1.html(d3_html_content, height=component_height_for_iframe + 250, width=component_width_for_iframe +200)


    # Removed Matplotlib bulk download button and logic as requested.
    # if st.button("Generate and Download All Gauge Images (0-99) (Matplotlib)", key="download_all_matplotlib_gauges_button"):
    #     with st.spinner("Generating Matplotlib gauge images... This may take a moment."):
    #         zip_buffer = io.BytesIO()
    #         with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATE, False) as zipf:
    #             for val in range(100):
    #                 if st.session_state['gauge_type'] == "Round" or st.session_state['gauge_type'] == "Round Segmented":
    #                     img_buffer = create_gauge_image(
    #                         value=val,
    #                         size_x=st.session_state['output_width'],
    #                         size_y=st.session_state['output_height'],
    #                         active_color=st.session_state['active_color'],
    #                         inactive_color=st.session_state['inactive_color'],
    #                         bg_color=st.session_state['bg_color'],
    #                         gauge_name=st.session_state['gauge_name'],
    #                         show_name=st.session_state['show_name'],
    #                         show_value=st.session_state['show_value'],
    #                         image_format="png",
    #                         gauge_thickness_pixels=int(st.session_state['gauge_thickness'] * min(st.session_state['output_width'], st.session_state['output_height']) / 2),
    #                         gauge_start_angle_deg=st.session_state['start_angle'],
    #                         gauge_end_angle_deg=st.session_state['end_angle'],
    #                         fill_direction=st.session_state['fill_direction'],
    #                         output_dpi=100,
    #                         gauge_type=st.session_state['gauge_type'].replace("Round ", "").lower(), # Convert to "continuous" or "segmented"
    #                         num_segments=st.session_state['num_segments'],
    #                         segment_gap_deg=st.session_state['segment_gap_deg'],
    #                         is_3d=st.session_state['is_3d'],
    #                         gauge_value_color=st.session_state['gauge_value_color'], # Pass value color
    #                         gauge_name_color=st.session_state['gauge_name_color'] # Pass name color
    #                     )
    #                 elif st.session_state['gauge_type'] == "Linear" or st.session_state['gauge_type'] == "Linear Segmented":
    #                     img_buffer = create_linear_gauge_image(
    #                         value=val,
    #                         size_x=st.session_state['output_width'],
    #                         size_y=st.session_state['output_height'],
    #                         active_color=st.session_state['active_color'],
    #                         inactive_color=st.session_state['inactive_color'],
    #                         bg_color=st.session_state['bg_color'],
    #                         gauge_name=st.session_state['gauge_name'],
    #                         show_name=st.session_state['show_name'],
    #                         show_value=st.session_state['show_value'],
    #                         image_format="png",
    #                         linear_thickness_pixels=st.session_state['linear_thickness'],
    #                         orientation=st.session_state['linear_orientation'],
    #                         num_segments=st.session_state['linear_num_segments'],
    #                         segment_gap_pixels=st.session_state['linear_segment_gap_pixels'],
    #                         tip_style=st.session_state['tip_style'],
    #                         is_3d=st.session_state['is_3d'],
    #                         gauge_value_color=st.session_state['gauge_value_color'], # Pass value color
    #                         gauge_name_color=st.session_state['gauge_name_color'] # Pass name color
    #                     )
    #                 zipf.writestr(f"{val:02d}_{st.session_state['gauge_type'].lower().replace(' ', '_')}.png", img_buffer.getvalue())
    #         zip_buffer.seek(0)
    #         st.download_button(
    #             label="Click to Download All Gauges ZIP (Matplotlib)",
    #             data=zip_buffer,
    #             file_name="all_matplotlib_gauge_images.zip",
    #             mime="application/zip",
    #             key="final_all_matplotlib_download_button"
    #         )
    #         st.success("All Matplotlib gauge images generated and ready for download!")

with selected_tab_title_obj[1]: # ICL Optimizer Tab
    st.title("ICL File Address Planner")

    files = st.file_uploader("Upload ICL files", type="icl", accept_multiple_files=True)
    start_block = st.number_input("Start Block (inclusive)", 0, 9999, 32, help="The first available memory block for allocation.")
    end_block = st.number_input("End Block (inclusive)", start_block, 9999, 63, help="The last available memory block for allocation.")

    if files:
        allocation = []
        overlaps = []
        # Matplotlib imports are already at the top level now.

        block_size = 256 * 1024  # 256 KB per block for DWIN

        def extract_block_from_filename(filename):
            try:
                numeric_part = filename.split('_')[0].split('.')[0]
                return int(numeric_part)
            except ValueError:
                return 0

        sorted_files = sorted(files, key=lambda f: extract_block_from_filename(f.name))

        n_blocks = end_block - start_block + 1
        if n_blocks <= 0:
            st.error("Error: End Block must be greater than or equal to Start Block.")
            st.stop()
        
        block_states = np.zeros(n_blocks, dtype=int) 

        st.write("### Original Address Allocation Check")

        for file in sorted_files:
            filename = file.name
            file.seek(0)
            size_bytes = len(file.read())
            file.seek(0)

            blocks_needed = int(np.ceil(size_bytes / block_size))
            start_from_filename = extract_block_from_filename(filename)
            end_from_filename = start_from_filename + blocks_needed - 1

            overlap_current_file = False
            
            if start_from_filename < start_block or end_from_filename > end_block:
                overlap_current_file = True
                overlaps.append(filename)
                
            if not overlap_current_file:
                for blk in range(start_from_filename, end_from_filename + 1):
                    idx = blk - start_block
                    if idx >= 0 and idx < n_blocks:
                        if block_states[idx] == 1:
                            overlap_current_file = True
                            if filename not in overlaps:
                                overlaps.append(filename)
                            break
                    else:
                        pass
            
            for blk in range(start_from_filename, end_from_filename + 1):
                idx = blk - start_block
                if idx >= 0 and idx < n_blocks:
                    if overlap_current_file:
                        block_states[idx] = 2
                    elif block_states[idx] == 0:
                        block_states[idx] = 1
                
                allocation.append({
                    "File": filename,
                    "Size KB": round(size_bytes / 1024, 1),
                    "Blocks": blocks_needed,
                    "Original Start": start_from_filename,
                    "Original End": end_from_filename,
                    "Status": "Overlap/Out of Range" if overlap_current_file else "Valid"
                })

        st.dataframe(allocation)

        if overlaps:
            st.error(f"Overlapping or out-of-range files detected in original planning: {', '.join(overlaps)}")
        else:
            st.success("No overlaps or out-of-range issues detected in original planning.")

        st.write("## Optimized (Non-Overlapping) Packing Proposal")

        proposal = []
        used_blocks_opt = set()
        cur_block = start_block
        file_map = {}

        for file in sorted_files:
            file.seek(0)
            size_bytes = len(file.read())
            file.seek(0)
            blocks_needed = int(np.ceil(size_bytes / block_size))

            while any(b in used_blocks_opt for b in range(cur_block, cur_block + blocks_needed)):
                cur_block += 1
                if cur_block + blocks_needed - 1 > end_block:
                    break

            new_start = cur_block
            new_end = new_start + blocks_needed - 1

            if new_end <= end_block:
                used_blocks_opt.update(range(new_start, new_end + 1))
                
                original_name_parts = file.name.split('_', 1)
                if len(original_name_parts) > 1:
                    new_filename = f"{new_start:02d}_{original_name_parts[1]}" 
                else:
                    ext = file.name.split('.')[-1]
                    new_filename = f"{new_start:02d}.{ext}"

                proposal.append({
                    "File": file.name,
                    "Size KB": round(size_bytes / 1024, 1),
                    "Blocks": blocks_needed,
                    "Proposed Start": new_start,
                    "Proposed End": new_end,
                    "New Filename": new_filename
                })
                file_map[file.name] = new_filename
                cur_block = new_end + 1
            else:
                proposal.append({
                    "File": file.name,
                    "Size KB": round(size_bytes / 1024, 1),
                    "Blocks": blocks_needed,
                    "Proposed Start": "-",
                    "Proposed End": "OUT OF SPACE",
                    "New Filename": "N/A"
                })

        st.dataframe(proposal)

        st.write("### Download All Files with Optimized Names (optional)")
        
        if any(item["Proposed Start"] != "-" for item in proposal):
            if st.button("Download Renamed ZIP"):
                zip_buffer_download = io.BytesIO()
                with zipfile.ZipFile(zip_buffer_download, "w", zipfile.ZIP_DEFLATE, False) as zipf:
                    for file in sorted_files:
                        if file.name in file_map:
                            newname = file_map[file.name]
                            file.seek(0)
                            zipf.writestr(newname, file.read())
                
                zip_buffer_download.seek(0)
                st.download_button(
                    "Download ZIP",
                    zip_buffer_download,
                    file_name="icl_optimized_renamed.zip",
                    mime="application/zip"
                )
        else:
            st.info("No files were successfully allocated within the specified block range for optimized download.")

        st.write("### Block Allocation Map")
        
        fig, ax = plt.subplots(figsize=(10, 3))

        colors = {0: 'lightgray', 1: 'dodgerblue', 2: 'crimson'}
        labels = {0: 'Free', 1: 'Occupied', 2: 'Overlap/Out of Range'}

        for blk_idx in range(n_blocks):
            block_num = start_block + blk_idx
            ax.barh(0, 1, left=block_num, color=colors[block_states[blk_idx]], edgecolor='k', height=0.8)

        ax.set_xlim(start_block, end_block + 1)
        ax.set_xlabel("Flash Block Number")
        ax.set_yticks([])
        ax.set_title("Memory Block Allocation (Red=Overlap/Out of Range, Blue=Occupied, Gray=Free)")

        patches = [plt.Rectangle((0, 0), 1, 1, fc=colors[key], edgecolor='k') for key in sorted(colors.keys())]
        ax.legend(patches, [labels[key] for key in sorted(colors.keys())], bbox_to_anchor=(1.05, 1), loc='upper left')

        st.pyplot(fig)
        plt.close(fig)


# Custom CSS for better appearance (optional, but good practice)
st.markdown("""
<style>
    /* Main container padding */
    .stApp > header {
        display: none; /* Hide Streamlit header */
    }
    .stApp {
        padding: 2rem;
    }
    /* Sidebar styling */
    .st-emotion-cache-1lcbmhc { /* This targets the sidebar container */
        background-color: #f0f2f6;
        border-right: 1px solid #e0e0e0;
        padding: 1.5rem;
        border-radius: 0.75rem;
    }
    .st-emotion-cache-1lcbmhc h2 {
        color: #333;
        font-size: 1.4rem;
        margin-bottom: 1rem;
    }
    .st-emotion-cache-1lcbmhc .stTextInput label,
    .st-emotion-cache-1lcbmhc .stNumberInput label,
    .st-emotion-cache-1lcbmhc .stColorPicker label,
    .st-emotion-cache-1lcbmhc .stRadio label,
    .st-emotion-cache-1lcbmhc .stSlider label {
        font-weight: bold;
        color: #555;
    }
    /* Main title */
    h1 {
        color: #1a1a1a;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    /* Subheaders */
    h2 {
        color: #333;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
    /* Button styling */
    .stButton > button {
        width: 100%;
        border-radius: 0.75rem;
        background-color: #007bff; /* Primary blue */
        color: white;
        font-weight: bold;
        padding: 0.8rem 1.5rem;
        border: none;
        box-shadow: 0 4px 10px rgba(0, 123, 255, 0.2);
        transition: background-color 0.3s ease, transform 0.2s ease;
        cursor: pointer;
        font-size: 1.1rem;
    }
    .stButton > button:hover {{
        background-color: #0056b3;
    }}
    .stButton > button:active {{
        background-color: #004085;
    }}
    /* Info and Success messages */
    .stAlert {{
        border-radius: 0.5rem;
        margin-top: 1rem;
    }}
    /* Image container for preview */
    .stImage {{
        text-align: center;
        margin-top: 1rem;
    }}
</style>
""", unsafe_allow_html=True)
