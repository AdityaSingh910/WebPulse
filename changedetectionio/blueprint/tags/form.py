# Modified 2026 for the simplified (academic) fork of changedetection.io - optional features removed, see CHANGES.md
from wtforms import (
    Form,
    RadioField,
    StringField,
    SubmitField,
    TextAreaField,
    validators,
)
from wtforms.fields.simple import BooleanField
from flask_babel import lazy_gettext as _l

from changedetectionio.blueprint.tags.colour import CSS_HEX_COLOUR_REGEX
from changedetectionio.notification import (
    GROUP_NOTIFICATION_MODE_ADD,
    GROUP_NOTIFICATION_MODE_FALLBACK,
    GROUP_NOTIFICATION_MODE_REPLACE,
)
from changedetectionio.processors.restock_diff.forms import processor_settings_form as restock_settings_form
class group_restock_settings_form(restock_settings_form):
    overrides_watch = BooleanField(_l('Activate for individual watches in this tag/group?'), default=False)
    url_match_pattern = StringField(_l('Auto-apply to watches with URLs matching'),
                                    render_kw={"placeholder": _l("e.g. *://example.com/* or github.com/myorg")})
    # Rendered into a <style> block, so only a plain hex colour is accepted, see colour.py
    tag_colour = StringField(_l('Tag colour'),
                             default='',
                             validators=[validators.Optional(),
                                         validators.Regexp(CSS_HEX_COLOUR_REGEX,
                                                           message=_l('Must be a hex colour, for example #4f8ef7'))])
    # The first choice is how groups have always worked, the other two send the group's
    # notification on its own - see notification_service.notification_senders()
    notification_group_mode = RadioField(
        _l("Send this group's notifications"),
        choices=[
            (GROUP_NOTIFICATION_MODE_FALLBACK, _l("Only if the watch has none of its own")),
            (GROUP_NOTIFICATION_MODE_ADD, _l("As well as the watch's own")),
            (GROUP_NOTIFICATION_MODE_REPLACE, _l("Instead of the watch's own")),
        ],
        default=GROUP_NOTIFICATION_MODE_FALLBACK,
    )

class SingleTag(Form):

    name = StringField(_l('Tag name'), [validators.InputRequired()], render_kw={"placeholder": _l("Name")})
    save_button = SubmitField(_l('Save'), render_kw={"class": "pure-button pure-button-primary"})
