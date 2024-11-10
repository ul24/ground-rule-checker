from clang import cindex
import re
import debuginfo

class GroundRuleChecker:
    DETECT_VOID_FUNCTION = True
    DETECT_WRONG_NAME_FUNCTION = True
    DETECT_LONG_INDENT_FUNCTION = True
    DETECT_SIZE_OF_ENUM = True
    DETECT_WRONG_TYPEDEF_ENUM = True
    DETECT_WRONG_COMMENT = True
    DETECT_UNINIT_LOCAL_VARIABLE = True
    DETECT_WRONG_COMMIT_TITLE = True

    INDENT_LIMIT = 4
    ENUM_ELEMENT_MIN = 3

    def __init__(self, commit_title, files):
        self.commit_title = commit_title
        self.files = files

    def make_ast_of_file(self):
        index = cindex.Index.create()
        return index.parse(self.file_path)

    def detect_void_function(self):
        """
        Ground rule: void func (arg ......)

        Reason: void function does not give any information about error to caller
        """
        void_functions = []
        excluded_names = ['_cb', '_callback', '_handler']

        for node in self.translation_unit.cursor.get_children():
            if node.location.file.name != self.file_path:
                continue

            if node.kind != cindex.CursorKind.FUNCTION_DECL:
                continue

            if node.kind == cindex.CursorKind.CONSTRUCTOR:
                continue

            if node.kind == cindex.CursorKind.DESTRUCTOR:
                continue

            return_type = node.result_type.spelling
            function_name = node.spelling

            if any(function_name.endswith(excluded_name) for excluded_name in excluded_names):
                continue

            if return_type == 'void':
                void_functions.append((function_name, node.location.line))

            return void_functions

    def is_snake_case(self, name):
        return re.match(r'^_*[a-z0-9]+(_[a-z0-9]+)*$', name) is not None

    def detect_wrong_name_function(self):
        """
        Ground rule: int FuncName(args ......)

        Reason: c function name is basically using snake style
        """
        wrong_name_functions = []
        for node in self.translation_unit.cursor.get_children():
            if node.location.file.name != self.file_path:
                continue

            if node.kind != cindex.CursorKind.FUNCTION_DECL:
                continue

            function_name = node.spelling
            if not self.is_snake_case(function_name):
                wrong_name_functions.append((function_name, node.location.line))

        return wrong_name_functions

    def calculate_function_indent(self, func_node):
        start_line = func_node.extent.start.line
        end_line = func_node.extent.end.line

        max_indent_level = 0
        indent_line_num = 1
        indent_info = []
        for line_num in range(start_line, end_line + 1):
            line_content = self.file_lines[line_num - 1]
            indent_level = len(line_content) - len(line_content.lstrip('\t'))

            if max_indent_level < indent_level:
                max_indent_level = indent_level
                indent_line_num = line_num

        if max_indent_level >= self.INDENT_LIMIT:
            indent_info.append((indent_line_num, max_indent_level))

        return indent_info

    def detect_long_indent_function(self):
        """
        Ground rule: if () 
                        for ()
                            if ()
                                for ()
        Reason: Long indentation makes code difficult to understand
        """
        long_indent_functions = []
        for node in self.translation_unit.cursor.get_children():
            if node.location.file.name != self.file_path:
                continue

            if node.kind != cindex.CursorKind.FUNCTION_DECL:
                continue

            indent_info = self.calculate_function_indent(node)
            if not indent_info:
                continue

            function_name = node.spelling
            for indent_line_num, indent_level in indent_info:
                long_indent_functions.append((function_name, indent_line_num, indent_level))
    
        return long_indent_functions

    def detect_small_size_of_enum(self):
        """
        Ground rule: enum {
                       ENUM1,
                       ENUM2,
                 }
        Reason: Boolean is sufficient if there are only two options or less than two
        """
        small_size_enums = []
        for node in self.translation_unit.cursor.get_children():
            if node.location.file.name != self.file_path:
                continue
            
            if node.kind != cindex.CursorKind.ENUM_DECL:
                continue

            enum_name = node.spelling
            start_line = node.extent.start.line

            elements = [child for child in node.get_children() if child.kind == cindex.CursorKind.ENUM_CONSTANT_DECL]

            if len(elements) < self.ENUM_ELEMENT_MIN:
                small_size_enums.append((enum_name, start_line, len(elements)))

        return small_size_enums

    def detect_wrong_typedef_enum(self):
        """
        Ground rule: typedef enum {
                       ENUM1,
                       ENUM2,
                       ENUM3,
                 } enum_type
        Reason: Typedef with enum type should have suffix '_e'
        """

        wrong_typedef_enums = []
        for node in self.translation_unit.cursor.get_children():
            if node.location.file.name != self.file_path:
                continue
            
            if node.kind != cindex.CursorKind.TYPEDEF_DECL:
                continue

            base_type = node.type.get_canonical().kind
            if base_type != cindex.TypeKind.ENUM:
                continue

            if node.spelling.endswith('_e'):
                continue

            wrong_typedef_enums.append((node.spelling, node.location.line))

        return wrong_typedef_enums

    def is_valid_comment(self, comment_text):
        pattern = r'^/\*+[\s\S]*?\s*\*/$'
        return bool(re.match(pattern, comment_text.strip()))

    def detect_wrong_comment(self):
        """
        Ground rule: // comment1
                     // comment2
        Reason: Boolean is sufficient if there are only two options or less than two
        """
        wrong_comments = []
        for token in self.translation_unit.get_tokens(extent=self.translation_unit.cursor.extent):
            if token.kind != cindex.TokenKind.COMMENT:
                continue

            if not self.is_valid_comment(token.spelling):
                wrong_comments.append((token.location.line))

        return wrong_comments

    def is_initialized_variable(self, variable_node):
        for child_node in variable_node.get_children():
            if child_node.kind in (cindex.CursorKind.CSTYLE_CAST_EXPR,
                                   cindex.CursorKind.CALL_EXPR,
                                   cindex.CursorKind.INTEGER_LITERAL,
                                   cindex.CursorKind.FLOATING_LITERAL,
                                   cindex.CursorKind.STRING_LITERAL,
                                   cindex.CursorKind.UNEXPOSED_EXPR,
                                   cindex.CursorKind.BINARY_OPERATOR):
                return True

        return False

    def find_local_variable_from_decl_stmt(self, decl_stmt_node):
        local_variables = []

        for child_node in decl_stmt_node.get_children():
            if child_node.kind == cindex.CursorKind.VAR_DECL:
                local_variables.append((child_node))

        return local_variables

    def find_local_variable_from_compound_stmt(self, compound_stmt_node):
        local_variables = []

        for child_node in compound_stmt_node.get_children():
                if child_node.kind == cindex.CursorKind.VAR_DECL:
                    local_variables.append((child_node))
                elif child_node.kind == cindex.CursorKind.DECL_STMT:
                    local_variables += self.find_local_variable_from_decl_stmt(child_node) 

        return local_variables

    def detect_uninit_local_variable(self):
        """
        Ground rule: int x;
        Reason: uninitalized local variable has trash value
        """
        uninit_variables = []
        for node in self.translation_unit.cursor.get_children():
            if node.location.file.name != self.file_path:
                continue

            if node.kind != cindex.CursorKind.FUNCTION_DECL:
                continue

            function_name = node.spelling
            for child_node in node.get_children():
                local_variables = []
                
                if child_node.kind == cindex.CursorKind.VAR_DECL:
                    local_variables.append((child_node))
                elif child_node.kind == cindex.CursorKind.COMPOUND_STMT:
                    local_variables += self.find_local_variable_from_compound_stmt(child_node)
                else:
                    continue

                for local_variable_node in local_variables:
                    var_name = local_variable_node.spelling
                    line_num = local_variable_node.location.line

                    if not self.is_initialized_variable(local_variable_node):
                        uninit_variables.append((function_name, var_name, line_num))

        return uninit_variables

    def detect_code_smell_file(self):
        print("==== {} ====".format(self.file_path))

        if self.DETECT_VOID_FUNCTION:
            self.report_detected("VOID FUNCTION", self.detect_void_function())

        if self.DETECT_WRONG_NAME_FUNCTION:
            self.report_detected("WRONG NAME FUNCTION", self.detect_wrong_name_function())

        if self.DETECT_LONG_INDENT_FUNCTION:
            self.report_detected("LONG INDENT FUNCTION", self.detect_long_indent_function())

        if self.DETECT_SIZE_OF_ENUM:
            self.report_detected("SMALL SIZE ENUM", self.detect_small_size_of_enum())

        if self.DETECT_WRONG_TYPEDEF_ENUM:
            self.report_detected("WRONG TYPEDEF ENUM", self.detect_wrong_typedef_enum())

        if self.DETECT_WRONG_COMMENT:
            self.report_detected("WRONG COMMENT", self.detect_wrong_comment())

        if self.DETECT_UNINIT_LOCAL_VARIABLE:
            self.report_detected("UNINITALIZED LOCAL VARIABLE", self.detect_uninit_local_variable())

        print("")

    def detect_wrong_commit_title(self):
        if not self.commit_title:
            print("== Failed to verify commit title (empty title) ==");
            return
    
        if self.commit_title[0].upper() == self.commit_title[0] and ':' not in self.commit_title:
            return
    
        pattern = r'(?:(?:[\w]+:)|(?:[\w]+: [\w]+:))( )(?=[A-Z][^:]*)?'  
        match = re.search(pattern, self.commit_title)
        if match:  
            return
       
        self.commit_title = title.replace('\n', '')
        print("==== {} ====".format(self.commit_title))
        print("== Commit title should be start with Uppercase or module_name: ==")
        print("")

    def get_all_lines_of_file(self):
        lines_of_file = []
        try:    
            with open(self.file_path, 'r') as file:
                for line in file:
                    lines_of_file.append(line.rstrip('\n'))
    
            debuginfo.print_debug_info("Read {} lines from {}".format(len(lines_of_file), self.file_path))
        except Exception as e:
            print("Failed to read file {}: {}".format(self.file_path, e))
    
        return lines_of_file

    def detect_code_smells(self):
        if self.DETECT_WRONG_COMMIT_TITLE and self.commit_title != None:
            self.detect_wrong_commit_title()

        for file_path in self.files:
            self.file_path = file_path
            self.file_lines = self.get_all_lines_of_file()
            self.translation_unit = self.make_ast_of_file()
            self.detect_code_smell_file()

    def report_detected(self, name, result):
        if result is None:
            return

        if len(result) == 0:
            return

        print("== {} LIST ({} Cases) ==".format(name, len(result)))
        if result:
            for item in result:
                debuginfo.print_debug_info("{} : {}".format(self.file_path, item))
