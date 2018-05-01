import re

from harrier.build import slugify
from harrier.extensions import modify


@modify.pages('/index.md')
def modify_foo(page, config):
    content = page['content']
    headings = re.findall('^(#{1,2}) (.*)', page['content'], re.M)
    headings = [(f'{len(p)}-{slugify(h)}', h) for p, h in headings]
    for slug, heading in headings:
        observer = (
            f'<amp-position-observer on="enter:{slug}-spy.start;" layout="nodisplay" viewport-margins="0 90vh">'
            f'</amp-position-observer>'
        )
        content = re.sub('^(#{1,2} ' + heading + ')$', observer + r'\n\n\1', content, flags=re.M)
    page.update(
        headings=headings,
        content=content,
    )
    return page
