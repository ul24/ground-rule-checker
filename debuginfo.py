g_debug_mode=False

def print_debug_info(message):
    global g_debug_mode 
    if g_debug_mode:
        print("DEBUG: {}".format(message))

def set_debug_mode(debug_mode):
    global g_debug_mode
    g_debug_mode = debug_mode
