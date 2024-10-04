#git-parser

git grounding rule checker (Target: c language)

## Prerequisites

Before you begin, ensure you have met the following requirements:
- Ubuntu machine (tested in 18.04 LTS)
- Python (tested and checked in Python 2.7.17)
- clang and libclang (clang and libclang version should be met, tested in 6.0.0)

## Installation

### Step 1: Install 'python'

```bash
sudo apt-get update	#Update package lists
sudo apt install python2.7	#Install python 2.7 version
```

### Step 2: Install 'clang' and 'libclang'

```bash
sudo apt-get update	#Update package lists
sudo apt-get install clang libclang-dev -y	#Install clang and libclang
export LD_LIBRARY_PATH=$(llvm-config --libdir)	#Add environment variable (recommend to add this to .bashrc)

```

## Test Method

```bash
python main.py -r <repo path> -c <commit id> -d
#  -h, --help			show this help message and exit
#  -r REPO, --repo REPO		Absolute path to the Git repository, mandatory
#  -c COMMIT, --commit COMMIT	Commit ID to retrieve files from, optional
#                               If no option is entered, check all .c and .h files in the repository.
#				If option is entered, check the modified and newly created .c and .h files in the repository.
#  -d, --debug			Enable debug mode, optional
#				If option is entered, print specific information about code that violates ground rule such as file path and line number.
```

## Test Ground Rule
```bash
1. Function return type is not void type
2. Functoin name is snake style
3. Indention size should be smaller than 4
4. Enumeration should have at least 3 elements
5. TYPEDEF of enum should have suffix as '_e'
6. Comment type should be '/* */' instead of '//'
7. Commit title should be start with uppercase or 'module name:'.
   Module name can be entered at most 2. (This ground rule is checked when -c opion is active)
```
