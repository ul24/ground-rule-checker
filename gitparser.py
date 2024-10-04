from clang import cindex
import re
import debuginfo

DETECT_VOID_FUNCTION = True
DETECT_WRONG_NAME_FUNCTION = True
DETECT_LONG_INDENT_FUNCTION = True
DETECT_SIZE_OF_ENUM = True
DETECT_WRONG_TYPEDEF_ENUM = True
DETECT_WRONG_COMMENT = True

INDENT_LIMIT = 4
ENUM_ELEMENT_MIN = 3

def make_ast_of_file(file_path):
    index = cindex.Index.create()
    translation_unit = index.parse(file_path)

    return translation_unit

def detect_void_function(file_path, translation_unit):
    """
    Ground rule: void func (arg ......)

    Reason: void function does not give any information about error to caller
    """
    void_functions = []
    for node in translation_unit.cursor.get_children():
        if node.location.file.name != file_path:
            continue

        if node.kind != cindex.CursorKind.FUNCTION_DECL:
            continue

        if node.kind == cindex.CursorKind.CONSTRUCTOR:
            continue

        if node.kind == cindex.CursorKind.DESTRUCTOR:
            continue

        return_type = node.result_type.spelling
        function_name = node.spelling
        if return_type == 'void':
            void_functions.append((function_name, node.location.line))

    return void_functions

def is_snake_case(name):
    return re.match(r'^_*[a-z0-9]+(_[a-z0-9]+)*$', name) is not None

def detect_wrong_name_function(file_path, translation_unit):
    """
    Ground rule: int FuncName(args ......)

    Reason: c function name is basically using snake style
    """
    wrong_name_functions = []
    for node in translation_unit.cursor.get_children():
        if node.location.file.name != file_path:
            continue

        if node.kind != cindex.CursorKind.FUNCTION_DECL:
            continue

        function_name = node.spelling
        if not is_snake_case(function_name):
            wrong_name_functions.append((function_name, node.location.line))

    return wrong_name_functions

def calculate_function_indent(func_node, file_lines, indent_limit):
    start_line = func_node.extent.start.line
    end_line = func_node.extent.end.line

    max_indent_level = 0
    indent_line_num = 1
    indent_info = []
    for line_num in range(start_line, end_line + 1):
        line_content = file_lines[line_num - 1]
        indent_level = len(line_content) - len(line_content.lstrip('\t'))

        if max_indent_level < indent_level:
            max_indent_level = indent_level
            indent_line_num = line_num

    if max_indent_level >= indent_limit:
        indent_info.append((indent_line_num, max_indent_level))

    return indent_info

def detect_long_indent_function(file_path, file_lines, translation_unit):
    """
    Ground rule: if () 
                     for ()
                         if ()
                             for ()
    Reason: Long indentation makes code difficult to understand
    """
    global INDENT_LIMIT
    
    long_indent_functions = []
    for node in translation_unit.cursor.get_children():
        if node.location.file.name != file_path:
            continue

        if node.kind != cindex.CursorKind.FUNCTION_DECL:
            continue

        indent_info = calculate_function_indent(node, file_lines, INDENT_LIMIT)
        if not indent_info:
            continue

        function_name = node.spelling
        for indent_line_num, indent_level in indent_info:
            long_indent_functions.append((function_name, indent_line_num, indent_level))

    return long_indent_functions

def detect_small_size_of_enum(file_path, translation_unit):
    """
    Ground rule: enum {
                       ENUM1,
                       ENUM2,
                 }
    Reason: Boolean is sufficient if there are only two options or less than two
    """
    global ENUM_ELEMENT_MIN
    
    small_size_enums = []
    for node in translation_unit.cursor.get_children():
        if node.location.file.name != file_path:
            continue

        if node.kind != cindex.CursorKind.ENUM_DECL:
            continue
       
        enum_name = node.spelling
        start_line = node.extent.start.line

        elements = [child for child in node.get_children() if child.kind == cindex.CursorKind.ENUM_CONSTANT_DECL]
        element_count = len(elements)
        
        if element_count < ENUM_ELEMENT_MIN:
            small_size_enums.append((enum_name, start_line, element_count))

    return small_size_enums


def detect_wrong_typedef_enum(file_path, translation_unit):
    """
    Ground rule: typedef enum {
                       ENUM1,
                       ENUM2,
                       ENUM3,
                 } enum_type
    Reason: Typedef with enum type should have suffix '_e'
    """
    wrong_typedef_enums = []
    for node in translation_unit.cursor.get_children():
        if node.location.file.name != file_path:
            continue

        if node.kind != cindex.CursorKind.TYPEDEF_DECL:
            continue

        base_type = node.type.get_canonical().kind
        if base_type != cindex.TypeKind.ENUM:
            continue

        if node.spelling.endswith('_e'):
            continue

        enum_name = node.spelling
        line_num = node.location.line
        wrong_typedef_enums.append((enum_name, line_num))

    return wrong_typedef_enums

def is_valid_comment(comment_text):
    pattern = r'^/\*+[\s\S]*?\s*\*/$'
    return bool(re.match(pattern, comment_text.strip()))

def detect_wrong_comment(file_path, translation_unit):
    """
    Ground rule: // comment1
                 // comment2
    Reason: Boolean is sufficient if there are only two options or less than two
    """
#    file_extent = None
    wrong_comments = []
#    for cursor in translation_unit.cursor.walk_preorder():
#        if cursor.location.file and  cursor.location.file.name == file_path:
#            file_extent = cursor.extent
#            break

#    if file_extent is None:
#        return wrong_comments

    for token in translation_unit.get_tokens(extent=translation_unit.cursor.extent):
        if token.kind != cindex.TokenKind.COMMENT:
            continue

        comment_text = token.spelling
        line = token.location.line

        if not is_valid_comment(comment_text):
            wrong_comments.append((line))

    return wrong_comments

def detect_code_smells(file_path, file_lines):
    global DETECT_VOID_FUNCTION
    global DETECT_WRONG_NAME_FUNCTION
    global DETECT_LONG_INDENT_FUNCTION
    global DETECT_SIZE_OF_ENUM
    global DETECT_WRONG_TYPEDEF_ENUM
    global DETECT_WRONG_COMMENT

    detected = False

    translation_unit = make_ast_of_file(file_path)
    print("==== {} ====".format(file_path))

    if DETECT_VOID_FUNCTION:
        result = detect_void_function(file_path, translation_unit)

    print("== VOID FUNCTION LIST ({} Cases) ==".format(len(result)))
    if result:
        for func_name, line_num in result:
            debuginfo.print_debug_info("{} : {} : {}".format(file_path, line_num, func_name))

    if DETECT_WRONG_NAME_FUNCTION:
        result = detect_wrong_name_function(file_path, translation_unit)

    print("== WRONG NAME FUNCTION LIST ({} Cases) ==".format(len(result)))
    if result:
        for func_name, line_num in result:
            debuginfo.print_debug_info("{} : {} : {}".format(file_path, line_num, func_name))

    if DETECT_LONG_INDENT_FUNCTION:
        result = detect_long_indent_function(file_path, file_lines, translation_unit)

    print("== LONG INDENT FUNCTION LIST ({} Cases) ==".format(len(result)))
    if result:
        for func_name, line_num, indent_level in result:
            debuginfo.print_debug_info("{} : {} : {} (max indent = {})".format(file_path, line_num, func_name, indent_level))

    if DETECT_SIZE_OF_ENUM:
        result = detect_small_size_of_enum(file_path, translation_unit)

    print("== SMALL SIZE ENUM LIST ({} Cases) ==".format(len(result)))
    if result:
        for enum_name, line_num, element_count in result:
            debuginfo.print_debug_info("{} : {} : {} (#element = {})".format(file_path, line_num, enum_name, element_count))

    if DETECT_WRONG_TYPEDEF_ENUM:
        result = detect_wrong_typedef_enum(file_path, translation_unit)

    print("== WRONG TYPEDEF ENUM LIST ({} Cases) ==".format(len(result)))
    if result:
        for enum_name, line_num in result:
            debuginfo.print_debug_info("{} : {} : {}".format(file_path, line_num, enum_name))

    if DETECT_WRONG_COMMENT:
        result = detect_wrong_comment(file_path, translation_unit)

    print("== WRONG COMMENT LIST ({} Cases) ==".format(len(result)))
    if result:
        for line_num in result:
            debuginfo.print_debug_info("{} : {} : Invalid comment".format(file_path, line_num))

    print("")
