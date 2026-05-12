def run(args=None):
    import os
    from datetime import datetime

    filename = f"~/Pictures/screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    os.system(f'import "{os.path.expanduser(filename)}"')
