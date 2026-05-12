def run(args=None):
    import os
    os.system("pactl set-sink-mute @DEFAULT_SINK@ toggle")
