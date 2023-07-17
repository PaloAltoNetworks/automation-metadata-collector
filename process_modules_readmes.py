"""Process README.md files for each module and example
"""
import os
import re
import logging
from pathlib import Path
from typing import NamedTuple, Union, Optional, TypeVar, Generic, Callable
from urllib.request import urlopen 
import base64

import argparse
import frontmatter as fm

OUTPUT_EXTENSION = "md"

KNOWN_ACRYONYMS = [
    "alb",
    "asg",
    "gwlb",
    "nlb",
    "vpc",
    "tgw",
    "natgw",
    "nat",
    "lb",
    "http",
    "iam",
]

T = TypeVar('T')

logging.basicConfig(level=logging.DEBUG)


class NoFrontmatterError(Exception):
    """Raised when a README.md file does not contain a frontmatter section"""

    def __init__(self, message=None, filepath=None):
        message = message if message else "No frontmatter found in README.md file"
        super().__init__(message)
        self.message = message
        self.filepath = filepath

    def __str__(self):
        if self.filepath:
            return f"{self.message}: {self.filepath}"
        return self.message


class TFModule(NamedTuple):
    """Terraform Module (or Example)"""

    readme_contents: str
    title: str
    slug: str
    short_title: str
    cloud_id: str
    type: str
    source_file: str
    description: Optional[str]
    show_in_hub: bool
    # version: str

class OutputFile(NamedTuple):
    """Output file"""

    contents: str
    path: Path


def image_url_to_base64(url: str) -> bytes:
    """Convert an image at a URL to a base64 encoded string

    Args:
        url (str): URL of the image

    Returns:
        str: Base64 encoded string
    """
    return base64.b64encode(urlopen(url).read())


def save_image(b64image: bytes, image_name: str, directory: Path) -> None:
    """Save an image to a directory

    Args:
        b64image (bytes): Base64 encoded image
        image_name (str): Name of the image
        directory (Path): Directory to save the image to
    """
    image_path = directory / image_name
    image_path.write_bytes(base64.b64decode(b64image))


def extract_cloud_id(string: str) -> str:
    """Find the cloud ID from the source repository

    Args:
        string (str): String to search

    Returns:
        str: Cloud ID
    """
    match = re.search(r"-(aws|azure|google|gcp)", string)
    if not match:
        raise ValueError(f"Could not find cloud ID in string: {string}")
    cloud_id = match.group(1).replace("google", "gcp")
    return cloud_id


def get_meta(frontmatter: fm, key: str, default: Union[T, Callable[[any], T]] = None) -> T:
    """Get a value from the frontmatter or return a default value

    Args:
        frontmatter (frontmatter): Frontmatter object
        key (str): Key to search for
        default (Union[str, callable], optional): A value of function to return
            as the default if key doesn't exist in frontmatter. Defaults to None.

    Returns:
        str: Value of the key in the frontmatter or the default value
    """
    if key in frontmatter:
        return frontmatter[key]
    elif callable(default):
        return default()
    else:
        return default


def read_and_parse_readme_file(readme_file: Path) -> TFModule:
    """Read and parse the README.md file

    Args:
        readme_file (Path): Path to the README.md file

    Raises:
        NoFrontmatterError: Raised when the README.md file does not contain a frontmatter section

    Returns:
        TFModule: TFModule instance
    """
    logging.debug(f"Processing file: {readme_file}")
    readme_file_contents = readme_file.read_text()
    readme_parsed = fm.loads(readme_file_contents)
    readme_contents = readme_parsed.content
    frontmatter = readme_parsed.metadata
    slug = get_meta(frontmatter, "slug", readme_file.parent.name)
    title = get_meta(
        frontmatter, "title", lambda: re.search(r"^# (.*)", readme_contents).group(1)
    )
    cloud_id = get_meta(
        frontmatter, "cloudId", lambda: extract_cloud_id(readme_file.parts[0])
    )
    short_title = get_meta(
        frontmatter, "short_title", lambda: synthesize_short_title(slug)
    )
    module_type = get_meta(
        frontmatter, "type", lambda: determine_module_type(readme_file, readme_contents)
    )
    show_in_hub = get_meta(
        frontmatter, "show_in_hub", True
    )
    description = get_meta(
        frontmatter, "description", None
    )
    return TFModule(
        title=title,
        slug=slug,
        cloud_id=cloud_id,
        short_title=short_title,
        type=module_type,
        show_in_hub=show_in_hub,
        description=description,
        source_file=str(readme_file),
        readme_contents=readme_contents,
    )


def get_module_readme_files(module_directory: Path) -> list[TFModule]:
    """Get all README.md files and their contents from the source repository

    Args:
        source_repository (str): Path to the directory containing the source repository

    Returns:
        list: List of TFModule instances, one for each README.md file
    """
    result = []
    readme_files = module_directory.glob("*/README.md")
    for readme in readme_files:
        tf_module = read_and_parse_readme_file(readme)
        result.append(tf_module)
    return result


def set_new_frontmatter(module: TFModule) -> str:
    """Set new frontmatter for the README.md file

    Args:
        readme_contents (str): Contents of the README.md file

    Returns:
        str: New contents of the README.md file
    """
    frontmatter = fm.loads(module.readme_contents)
    frontmatter["id"] = module.slug
    frontmatter["title"] = module.title
    frontmatter["sidebar_label"] = module.short_title
    if module.description:
        frontmatter["description"] = module.description
    frontmatter["hide_title"] = True
    frontmatter["pagination_next"] = None
    frontmatter["pagination_prev"] = None
    frontmatter["keywords"] = [
        "pan-os",
        "panos",
        "firewall",
        "configuration",
        "terraform",
        "vmseries",
        "vm-series",
        module.cloud_id,
    ]
    return fm.dumps(frontmatter)


def escape_underscores_in_pre_tags(input_string):
    pattern = re.compile(r"<pre>(.*?)</pre>", re.DOTALL)
    repl_func = lambda match: "<pre>" + match.group(1).replace("_", "\\_") + "</pre>"
    return pattern.sub(repl_func, input_string)


def sanitize_readme_contents(readme_contents: str) -> str:
    sanitized = readme_contents.replace("<br>", "<br />").replace("<hr>", "<hr />")
    return escape_underscores_in_pre_tags(sanitized)


def capitalize_words_in_string(word_list, input_string):
    def replacer(match):
        return match.group(0).upper()

    for word in word_list:
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        input_string = pattern.sub(replacer, input_string)
    return input_string


def synthesize_short_title(slug: str) -> str:
    """Synthesize a short title from the slug

    Args:
        slug (str): Slug

    Returns:
        str: Short title
    """
    words = slug.replace("-", "_").split("_")
    short_title = capitalize_words_in_string(KNOWN_ACRYONYMS, " ".join(words).title())
    short_title = re.sub(r"vmseries", "VM-Series", short_title, flags=re.IGNORECASE)
    return short_title


def determine_module_type(readme_path: Path, readme_contents: str) -> str:
    """Get the type of module from the directory name

    Args:
        readme_path (Path): Path to the README.md file
        readme_contents (str): Contents of the README.md file

    Returns:
        str: Type of module
    """
    if readme_path.parts[-3] == "examples":
        # If execution reaches here, frontmatter for type was not explicitly set,
        # so we assume that this is not a Reference Architecture, and hence
        # set the type to be an Example, based on the path of this README file
        return "example"
    if readme_path.parts[-3] == "modules":
        # If execution reaches here, frontmatter for type was not explicitly set,
        # so we assume this is a module based on the path of this README file
        return "module"
    raise ValueError(f"Could not determine module type from path: {readme_path}")

def delete_markdown_files(directory: Path):
    """Delete all markdown files in the directory

    Args:
        directory (Path): Directory to search
    """
    md_files = directory.glob(f"*.md")
    mdx_files = directory.glob(f"*.mdx")
    png_files = directory.glob(f"*.png")
    for f in md_files:
        os.remove(f)
    for f in mdx_files:
        os.remove(f)
    for f in png_files:
        os.remove(f)


def download_images(module: TFModule) -> dict[str, bytes]:
    """Download images from the README.md file

    Args:
        module (TFModule): TFModule
    
    Returns:
        dict: Dictionary of image names and image contents
    """
    images = {}
    image_pattern = re.compile(r"!\[.*?\]\((.*?)\)")
    for match in image_pattern.finditer(module.readme_contents):
        image_url = match.group(1)
        image_name = image_url.split("/")[-1]
        images[image_name] = image_url_to_base64(image_url)
    return images


def replace_image_urls(readme_contents: str) -> str:
    """Replace image URLs with local image names

    Args:
        readme_contents (str): Contents of the README.md file

    Returns:
        str: Contents of the README.md file with local image names
    """
    image_pattern = re.compile(r"!\[.*?\]\((.*?)\)")
    for match in image_pattern.finditer(readme_contents):
        image_url = match.group(1)
        image_name = image_url.split("/")[-1]
        readme_contents = readme_contents.replace(image_url, image_name+".png")
    return readme_contents


def main(modules_directory: str, dest_directory: str, module_type: str = None):
    """Main function

    Args:
        modules_directory (str): Path to the modules directory
        dest_directory (str): Path to the destination directory
        module_type (str, optional): Process only modules of this type (module, example, refarch). Defaults to None.
    """
    dest_directory_path = Path(dest_directory)
    tf_modules = get_module_readme_files(Path(modules_directory))
    if module_type is not None: # if module_type is supplied at execution time, only process modules of that type
        tf_modules = [module for module in tf_modules if module.type == module_type]
    output_files: list[OutputFile] = []
    images: list[dict[str, bytes]] = []
    for module in tf_modules:
        if module.show_in_hub is False:
            continue
        readme_images = download_images(module)
        new_readme_contents = set_new_frontmatter(module)
        new_readme_contents = replace_image_urls(new_readme_contents)
        new_readme_contents = sanitize_readme_contents(new_readme_contents)
        dest_file = dest_directory_path / f"{module.slug}.{OUTPUT_EXTENSION}"
        output_files.append(OutputFile(new_readme_contents, dest_file))
        images.append(readme_images)
    dest_directory_path.mkdir(parents=True, exist_ok=True)
    delete_markdown_files(dest_directory_path)
    for output_file in output_files:
        output_file.path.write_text(output_file.contents)
    for image_dict in images:
        for image_name, image_contents in image_dict.items():
            save_image(image_contents, image_name+".png", dest_directory_path)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert README.md files to Docusaurus"
    )
    parser.add_argument(
        "--type", type=str, default=None, required=False, help="Process only modules of this type (module, example, refarch)"
    )
    parser.add_argument("modules_directory", type=str, help="Modules directory")
    parser.add_argument("dest_directory", type=str, help="Destination directory")

    args = parser.parse_args()

    main(args.modules_directory, args.dest_directory, args.type)
