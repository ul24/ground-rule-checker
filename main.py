import argparse
import subprocess
import os
import debuginfo
import gitparser
import re

def print_user_input(repo_path, commit_id):
    print("Repository Path: {}".format(repo_path))
    print("Commit ID: {}".format(commit_id))

def execute_git_command(command_str ,repo_path, commit_id):
    if command_str == 'diff-tree':
        command = ['git', '-C', repo_path, command_str, '--no-commit-id', '--name-status', '-r', commit_id]
    elif command_str == 'checkout':
        command = ['git', '-C', repo_path, command_str, commit_id]  
    elif command_str == 'log':
        git_dir = os.path.join(repo_path, '.git')
        git_dir_option = "--git-dir="+git_dir
        command = ['git', git_dir_option, command_str, '-n', '1', '--pretty=%s']  
    else:
        raise Exception("Unknown git command")

    result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = result.communicate()

    stdout = stdout.decode('utf-8')
    stderr = stderr.decode('utf-8')

    if result.returncode != 0:
        raise Exception("Error git command: {}".format(stderr))

    return stdout


def detect_wrong_commit_title(title):
    if not title:
        print("== Failed to verify commit title (empty title) ==");
        return

    if title[0].upper() == title[0] and ':' not in title:
        return

    pattern = r'(?:(?:[\w]+:)|(?:[\w]+: [\w]+:))( )(?=[A-Z][^:]*)?'  
    match = re.search(pattern, title)  
    if match:  
        return
   
    title = title.replace('\n', '')
    print("==== {} ====".format(title))
    print("== Commit title should be start with Uppercase or module_name: ==")
    print("")

def get_commit_added_and_modified_files(repo_path, commit_id):
    stdout = execute_git_command('checkout', repo_path, commit_id)
    stdout = execute_git_command('diff-tree', repo_path, commit_id)

    files = []
    for line in stdout.splitlines():
        status, file_path = line.split('\t')
        if status in ['A', 'M'] and file_path.endswith(('.c', '.h')):
            absolute_path = os.path.abspath(os.path.join(repo_path, file_path))
            files.append(absolute_path)

    stdout = execute_git_command('log', repo_path, commit_id)
    detect_wrong_commit_title(stdout)
    
    stdout = execute_git_command('checkout', repo_path, 'tizen')

    return files

def get_all_files(repo_path):
    found_files = []
    for root, dirs, files in os.walk(repo_path, followlinks=False):
        for file in files:
            if file.endswith(('.c', '.h')):
                file_path = os.path.join(root, file)
                print(file_path)
                found_files.append(file_path)

    return found_files;

def get_all_lines_of_file(file_path):
    lines_of_file = []
    try:    
        with open(file_path, 'r') as file:
            for line in file:
                lines_of_file.append(line.rstrip('\n'))

        debuginfo.print_debug_info("Read {} lines from {}".format(len(lines_of_file), file_path))
    except Exception as e:
        print("Failed to read file {}: {}".format(file_path, e))

    return lines_of_file

def main():
    parser = argparse.ArgumentParser(description="Retrieve files from a specific Git commit.")
    parser.add_argument('-r', '--repo', type=str, required=True, help='Path to the Git repository')
    parser.add_argument('-c', '--commit', type=str, required=False, help='Commit ID to retrieve files from')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug mode.')

    args = parser.parse_args()
    repo_path = args.repo
    commit_id = args.commit
    debuginfo.set_debug_mode(args.debug)

    print_user_input(repo_path, commit_id)

    if commit_id:
        files = get_commit_added_and_modified_files(repo_path, commit_id)
    else:
        files = get_all_files(repo_path)

    if not files:
        print("Cannot find C files found in repository path: {}".format(repo_path))
        return

    debuginfo.print_debug_info("Found {} c or h files".format(len(files)))

    for file_path in files:
        file_lines = get_all_lines_of_file(file_path)
        gitparser.detect_code_smells(file_path, file_lines)

if __name__ == "__main__":
    main()
