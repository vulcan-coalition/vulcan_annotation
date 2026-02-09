try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

from setuptools.command.build_py import build_py
import os
import shutil

# --- CUSTOM BUILD COMMAND ---
class CustomBuild(build_py):
    def run(self):
        # 1. Run the standard build (creates build/lib/vulcan_annotation/...)
        super().run()
        
        # 2. Define Paths
        # The destination inside the build directory
        # (This is where the package expects the files to be at runtime)
        dest_dir = os.path.join(self.build_lib, "vulcan_annotation", "js")
        
        # The source directory
        # (This will be 'js/src' in your local repo, OR just 'js/src' 
        # inside the tarball when someone installs from it)
        src_dir = "js/src"

        # 3. The Copy Logic
        if os.path.exists(src_dir):
            # Ensure the destination folder exists
            os.makedirs(os.path.dirname(dest_dir), exist_ok=True)
            
            # Remove existing artifact if present to ensure clean copy
            if os.path.exists(dest_dir):
                shutil.rmtree(dest_dir)
            
            # Copy the directory
            shutil.copytree(src_dir, dest_dir)
            print(f"CustomBuild: Copied {src_dir} -> {dest_dir}")
        else:
            print(f"CustomBuild Warning: Could not find {src_dir} to copy.")

setup(
    name="vulcan-annotation",
    version="3.1.9",
    author="Chatavut Viriyasuthee",
    author_email="chatavut@lab.ai",
    description="Vulcan annotation for structured data.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/vulcan-coalition/vulcan_annotation",
    packages=["vulcan_annotation"],
    include_package_data=True,
    cmdclass={
        'build_py': CustomBuild,
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.9',
    install_requires=[
        "shortuuid",
        "levenshtein"
    ]
)
