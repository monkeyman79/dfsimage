"""This module contains argparse customizations.

    :meta private:
"""

# pylint: skip-file
# flake8: noqa: C901

from typing import Optional, Any
from gettext import gettext as _

import re as _re

from .wildparse import argparse
from .wildparse.argparse import HelpFormatter, CustomizableHelpFormatter
from .wildparse.argparse import SUPPRESS

_SubParsersAction: Optional[Any] = None

if '_SubParsersAction' in dir(argparse):
    _SubParsersAction = argparse._SubParsersAction  # pylint: disable=protected-access


class MixUsageHelpFormatter(HelpFormatter):
    """Mix optional and positional arguments in usage."""

    def _format_usage(self, usage, actions, groups, prefix):
        if prefix is None:
            prefix = _('usage: ')

        # helper for wrapping lines
        def get_lines(parts, indent, prefix=None):
            lines = []
            line = []
            if prefix is not None:
                line_len = len(prefix) - 1
            else:
                line_len = len(indent) - 1
            for part in parts:
                if line_len + 1 + len(part) > text_width and line:
                    lines.append(indent + ' '.join(line))
                    line = []
                    line_len = len(indent) - 1
                line.append(part)
                line_len += len(part) + 1
            if line:
                lines.append(indent + ' '.join(line))
            if prefix is not None:
                lines[0] = lines[0][len(indent):]
            return lines

        # if usage is specified, use that
        if usage is not None:
            prog = '%(prog)s' % dict(prog=self._prog)
            prog1 = prog.split()[0]
            usage = usage % dict(prog=self._prog)
            lines = usage.split('\n')
            out_lines = []

            text_width = self._width - self._current_indent
            for line in lines:
                if len(out_lines) != 0:
                    line = ' ' * len(prefix) + prog1 + ' ' + line
                if len(prefix) + len(line) > text_width:
                    match = _re.match(r'^(\s*\S*)(\s.*)$', line)
                    head = match[1]
                    tail = match[2]

                    # break usage into wrappable parts
                    part_regexp = (
                        r'\(.*?\)+(?=\s|$)|'
                        r'\[.*?\]+(?=\s|$)|'
                        r'\S+'
                    )

                    parts = _re.findall(part_regexp, tail)
                    indent = ' ' * (len(prefix) + len(prog) + 1)
                    out_lines.extend(get_lines([head] + parts, indent, prefix))

                else:
                    out_lines.append(line)

            usage = '\n'.join(out_lines)

        # if no optionals or positionals are available, usage is just prog
        elif usage is None and not actions:
            usage = '%(prog)s' % dict(prog=self._prog)

        # if optionals and positionals are available, calculate usage
        elif usage is None:
            prog = '%(prog)s' % dict(prog=self._prog)

            # split optionals from positionals
            optionals = []
            positionals = []
            for action in actions:
                if action.option_strings:
                    optionals.append(action)
                else:
                    positionals.append(action)

            # build full usage string
            format = self._format_actions_usage
            action_usage = format(actions, groups)
            usage = ' '.join([s for s in [prog, action_usage] if s])

            # wrap the usage parts if it's too long
            text_width = self._width - self._current_indent
            if len(prefix) + len(usage) > text_width:

                # break usage into wrappable parts
                part_regexp = (
                    r'\(.*?\)+(?=\s|$)|'
                    r'\[.*?\]+(?=\s|$)|'
                    r'\S+'
                )
                opt_usage = format(actions, groups)
                pos_usage = ''
                opt_parts = _re.findall(part_regexp, opt_usage)
                pos_parts = _re.findall(part_regexp, pos_usage)
                assert ' '.join(opt_parts) == opt_usage
                assert ' '.join(pos_parts) == pos_usage

                # if prog is short, follow it with optionals or positionals
                if len(prefix) + len(prog) <= 0.75 * text_width:
                    indent = ' ' * (len(prefix) + len(prog) + 1)
                    if opt_parts:
                        lines = get_lines([prog] + opt_parts, indent, prefix)
                        lines.extend(get_lines(pos_parts, indent))
                    elif pos_parts:
                        lines = get_lines([prog] + pos_parts, indent, prefix)
                    else:
                        lines = [prog]

                # if prog is long, put it on its own line
                else:
                    indent = ' ' * len(prefix)
                    parts = opt_parts + pos_parts
                    lines = get_lines(parts, indent)
                    if len(lines) > 1:
                        lines = []
                        lines.extend(get_lines(opt_parts, indent))
                        lines.extend(get_lines(pos_parts, indent))
                    lines = [prog] + lines

                # join lines into usage
                usage = '\n'.join(lines)

        # prefix with 'usage:'
        return '%s%s\n\n' % (prefix, usage)


class GroupUsageHelpFormatter(HelpFormatter):
    """Just show options group name in usage."""

    def _format_actions_usage(self, actions, groups):
        # find group indices and identify actions in groups
        group_actions = set()
        inserts = {}
        found_groups = set()
        for group in groups:
            try:
                start = actions.index(group._group_actions[0])
            except ValueError:
                continue
            else:
                end = start + len(group._group_actions)
                if actions[start:end] == group._group_actions:
                    for action in group._group_actions:
                        group_actions.add(action)
                    if not group.required:
                        if start in inserts:
                            inserts[start] += ' ['
                        else:
                            inserts[start] = '['
                        if end in inserts:
                            inserts[end] += ']'
                        else:
                            inserts[end] = ']'
                    else:
                        if start in inserts:
                            inserts[start] += ' ('
                        else:
                            inserts[start] = '('
                        if end in inserts:
                            inserts[end] += ')'
                        else:
                            inserts[end] = ')'
                    for i in range(start + 1, end):
                        inserts[i] = '|'

        # collect all actions format strings
        parts = []
        for i, action in enumerate(actions):

            container = action.container
            if ((not hasattr(container, "group_usage") or container.group_usage)
                    and action.option_strings):
                if container not in found_groups:
                    found_groups.add(container)
                    parts.append(container.title)
                    if inserts.get(i):
                        ins = inserts[i]
                        if ins[-1] != '[':
                            inserts[i] += ' ['
                    else:
                        inserts[i] = "["
                    inserts[i+1] = "]"
                else:
                    parts.append(None)
                    if inserts.get(i) is not None:
                        inserts.pop(i)
                    inserts[i+1] = "]"

            # suppressed arguments are marked with None
            # remove | separators for suppressed arguments
            elif action.help is SUPPRESS:
                parts.append(None)
                if inserts.get(i) == '|':
                    inserts.pop(i)
                elif inserts.get(i + 1) == '|':
                    inserts.pop(i + 1)

            # produce all arg strings
            elif not action.option_strings:
                default = self._get_default_metavar_for_positional(action)
                part = self._format_args(action, default)

                # if it's in a group, strip the outer []
                if action in group_actions:
                    if part[0] == '[' and part[-1] == ']':
                        part = part[1:-1]

                # add the action string to the list
                parts.append(part)

            # produce the first way to invoke the option in brackets
            else:
                option_string = action.option_strings[0]

                # if the Optional doesn't take a value, format is:
                #    -s or --long
                if action.nargs == 0:
                    part = '%s' % option_string

                # if the Optional takes a value, format is:
                #    -s ARGS or --long ARGS
                else:
                    default = self._get_default_metavar_for_optional(action)
                    args_string = self._format_args(action, default)
                    part = '%s %s' % (option_string, args_string)

                # make it look optional if it's not required or in a group
                if not action.required and action not in group_actions:
                    part = '[%s]' % part

                # add the action string to the list
                parts.append(part)

        # insert things at the necessary indices
        for i in sorted(inserts, reverse=True):
            parts[i:i] = [inserts[i]]

        # join all the action items with spaces
        text = ' '.join([item for item in parts if item is not None])

        # clean up separators for mutually exclusive groups
        open = r'[\[(]'
        close = r'[\])]'
        text = _re.sub(r'(%s) ' % open, r'\1', text)
        text = _re.sub(r' (%s)' % close, r'\1', text)
        text = _re.sub(r'%s *%s' % (open, close), r'', text)
        text = _re.sub(r'\(([^|]*)\)', r'\1', text)
        text = text.strip()

        # return the text
        return text


class ArgsOnceHelpFormatter(HelpFormatter):
    """Show action arguments only once for short and long command form."""
    def _format_action_invocation(self, action):
        if not action.option_strings:
            default = self._get_default_metavar_for_positional(action)
            metavar, = self._metavar_formatter(action, default)(1)
            return metavar

        else:
            parts = []

            # if the Optional doesn't take a value, format is:
            #    -s, --long
            if action.nargs == 0:
                parts.extend(action.option_strings)

            # if the Optional takes a value, format is:
            #    -s ARGS, --long ARGS
            else:
                default = self._get_default_metavar_for_optional(action)
                args_string = self._format_args(action, default)
                option_index = len(action.option_strings)
                for option_string in action.option_strings:
                    option_index -= 1
                    if option_index == 0:
                        parts.append(self._format_option_with_args(option_string, args_string))
                    else:
                        parts.append(option_string)

            return ', '.join(parts)


# https://stackoverflow.com/questions/11070268/argparse-python-remove-subparser-list-in-help-menu
class NoSubparsersMetavarFormatter(HelpFormatter):
    """Hack for argparse help formatter to remove redundant list of subcommands."""

    def _format_action(self, action):
        result = super()._format_action(action)  # pylint: disable=no-member
        if isinstance(action, _SubParsersAction):
            # fix indentation on first line
            return "%*s%s" % (self._current_indent, "", result.lstrip())
        return result

    def _format_action_invocation(self, action):
        if isinstance(action, _SubParsersAction):
            # remove metavar and help line
            return ""
        return super()._format_action_invocation(action)  # pylint: disable=no-member

    def _iter_indented_subactions(self, action):
        try:
            get_subactions = action._get_subactions  # pylint: disable=protected-access
        except AttributeError:
            pass
        else:
            yield from get_subactions()


class MyHelpFormatter(NoSubparsersMetavarFormatter,
                      ArgsOnceHelpFormatter,
                      GroupUsageHelpFormatter,
                      MixUsageHelpFormatter,
                      CustomizableHelpFormatter):
    pass
