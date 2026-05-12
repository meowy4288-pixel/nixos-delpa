def run(args=None):
    import os
    os.system("pactl set-sink-volume @DEFAULT_SINK@ +5%")
