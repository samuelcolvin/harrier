import re
from harrier.extensions import modify, template


@template.contextfunction
def inline_css(ctx):
    p = ctx['site']['dist_dir'] / ctx['site']['theme_files']['theme/inline.css']
    css = p.read_text()
    css = re.sub('(sourceMappingURL=)', r'\1/theme/', css)
    return css.strip('\n\r\t ')

