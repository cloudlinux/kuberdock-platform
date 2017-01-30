
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import json

from tests_integration.lib.exceptions import NonZeroRetCodeException
from tests_integration.lib.utils import (
    assert_raises, assert_eq, hooks, POD_STATUSES)
from tests_integration.lib.pipelines import pipeline

PREDEFINED_APPLICATION_FILES = {
    "dokuwiki": "/tmp/kuberdock_predefined_apps/dokuwiki.yaml",
    "drupal": "/tmp/kuberdock_predefined_apps/drupal.yaml",
    "wordpress": "/tmp/kuberdock_predefined_apps/wordpress.yaml"
}


def _clear_pa_catalog(cluster):
    cluster.pas.delete_all()


def _check_pa_template(template, **expected_fields_values):
    """Check fields of template.

    1. Check that template has required set of fields.
    2. Check values of fields, specified in parameters.

    """
    errors = []

    def _check_fields_presence():
        fields = {"name", "id", "origin", "created", "modified", "template"}
        lost_fields = fields - set(template.keys())
        if lost_fields:
            errors.append("Template doesn't contain field(s) as follows: {}.".
                          format(", ".join(lost_fields)))

    def _wrong_field_value(field, expected, actual):
        errors.append("{} is supposed to be {}, but is {}.".
                      format(field.capitalize(), expected, actual))

    _check_fields_presence()

    for key, value in expected_fields_values.items():
        if value and template.get(key) != value:
            _wrong_field_value(key, value, template.get(key))

    if errors:
        raise InvalidTemplate("\n".join(errors))


def _pa_create(cluster, name, f=None, data=None, origin=None,
               validate=False, check_output=True):
    cmd = ["predefined-apps create --name '{}'".format(name)]
    # Situation "if not (bool(f) != bool(data))" is not handled here, because
    # in this case exception should be raised immediately by kdctl
    if f:
        cmd.append("-f {}".format(f))
    if data:
        cmd.append("'{}'".format(data))

    if origin:
        cmd.append("--origin '{}'".format(origin))

    if validate:
        cmd.append("--validate")

    _, out, _ = cluster.kdctl(" ".join(cmd), out_as_dict=True)
    if check_output:
        if not origin:
            origin = "unknown"
        _check_pa_template(out["data"], name=name, origin=origin)
    return out["data"]


def _pa_update(cluster, f=None, data=None, validate=False, **kwarg):
    cmd = ["predefined-apps update".format(f)]
    # Situation "if not (bool(f) != bool(data))" is not handled here, because
    # in this case exception should be raised immediately by kdctl
    if f:
        cmd.append("-f {}".format(f))
    if data:
        cmd.append("'{}'".format(data))

    for key, val in kwarg.items():
        cmd.append("--{} '{}'".format(key, val))
    if validate:
        cmd.append("--validate")
    cluster.kdctl(" ".join(cmd), out_as_dict=True)


def _pa_get(cluster, command="kdctl", file_only=False, **kwarg):
    commands = {
        "kdctl": cluster.kdctl,
        "kcli2": cluster.kcli2
    }
    cmd = ["predefined-apps get"]
    for key, val in kwarg.items():
        cmd.append("--{} '{}'".format(key, val))
    if file_only:
        cmd.append("--file-only")
        _, out, _ = commands[command](" ".join(cmd))
        return out
    else:
        _, out, _ = commands[command](" ".join(cmd), out_as_dict=True)
        return out["data"]


def _pa_delete(cluster, **kwarg):
    cmd = ["predefined-apps delete"]
    for key, val in kwarg.items():
        cmd.append("--{} '{}'".format(key, val))
    cluster.kdctl(" ".join(cmd))


@pipeline("PA_catalog")
@hooks(setup=_clear_pa_catalog)
def test_add_get_delete_predefined_application_template_by_name(cluster):
    # Check that PA template can be added from the file
    name = "my pa1"
    _pa_create(cluster, name, f=PREDEFINED_APPLICATION_FILES["dokuwiki"],
               check_output=True)

    # Check that PA template can be got by it's name (kdctl)
    template = _pa_get(cluster, command="kdctl", name=name)
    _check_pa_template(template, name=name, origin="unknown")

    # Check that PA template can be got by it's name (kcli2)
    template = _pa_get(cluster, command="kcli2", name=name)
    _check_pa_template(template, name=name, origin="unknown")

    # Check that PA can be deleted by it's name
    _pa_delete(cluster, name=name)
    with assert_raises(NonZeroRetCodeException, "Error: Unknown name my pa1"):
        _pa_get(cluster, command="kcli2", name=name)


@pipeline("PA_catalog")
@hooks(setup=_clear_pa_catalog)
def test_add_get_delete_predefined_application_template_by_id(cluster):
    # Check that PA template can be added from the cmd line
    _, template, _ = cluster.ssh_exec("master", "cat {}".format(
                                PREDEFINED_APPLICATION_FILES["drupal"]))
    name = "my pa2"
    template = _pa_create(cluster, name, data=template, check_output=True)

    # Check that PA template can be got by it's id (kdctl)
    id_ = template["id"]
    template = _pa_get(cluster, command="kdctl", id=id_)
    _check_pa_template(template, name=name, origin="unknown", id=id_)

    # Check that PA template can be got by it's id (kcli2)
    template = _pa_get(cluster, command="kcli2", id=id_)
    _check_pa_template(template, name=name, origin="unknown", id=id_)

    # Check that PA can be deleted by it's id's
    _pa_delete(cluster, id=id_)
    with assert_raises(NonZeroRetCodeException, "No such predefined app"):
        _pa_get(cluster, command="kdctl", id=id_)


@pipeline("PA_catalog")
@hooks(setup=_clear_pa_catalog)
def test_add_predefined_application_template_with_origin(cluster):
    name = "my pa with origin"
    origin = "kuberdock"
    _pa_create(cluster, name, f=PREDEFINED_APPLICATION_FILES["dokuwiki"],
               origin=origin, check_output=True)


@pipeline("PA_catalog")
@hooks(setup=_clear_pa_catalog)
def test_validate_yaml(cluster):
    # Check that --validate flag prevents creating invalid PA template
    with assert_raises(NonZeroRetCodeException, "Unable to parse template"):
        _pa_create(cluster, "incorrect pa",
                   data="incorrect: template\nexpression",
                   validate=True, check_output=False)

    # Check that --validate flag allows creating valid template
    name = 'correct pa'
    _pa_create(cluster, name, f=PREDEFINED_APPLICATION_FILES["dokuwiki"],
               validate=True, check_output=True)

    # Check that PA template list contains only "correct pa"
    _, out, _ = cluster.kdctl("predefined-apps list")
    templates = json.loads(out)["data"]
    assert_eq(len(templates), 1)
    assert_eq(templates[0]["name"], name)


@pipeline("PA_catalog", skip_reason="FIXME in AC-4743")
@hooks(setup=_clear_pa_catalog)
def get_only_yaml_part_of_pa_template(cluster):
    _, template, _ = cluster.ssh_exec("master", "cat {}".format(
        PREDEFINED_APPLICATION_FILES["drupal"]))
    name = "my pa"
    cluster.kdctl("predefined-apps create --name '{}' '{}'".
                  format(name, template))
    _, out, _ = cluster.kdctl("predefined-apps get --name '{}' --file-only".
                              format(name))
    assert_eq(out, template)


@pipeline("PA_catalog")
@hooks(setup=_clear_pa_catalog)
def test_listing_pa_templates(cluster):

    def _check_list_output(command):
        methods = {
            "kdctl": cluster.kdctl,
            "kcli2": cluster.kcli2
        }

        _, out, _ = methods[command]("predefined-apps list", out_as_dict=True)
        listed_templates = {t["name"]: t for t in out["data"]}
        assert_eq(len(listed_templates), len(templates))
        listed_names = [t for t in listed_templates]
        not_listed_names = []
        # Check that all PA templates added to Kuberdock are listed
        for template in templates:
            name = template["template name"]
            if name not in listed_names:
                not_listed_names.append(name)
        if not_listed_names:
            raise PATemplateNotInList(
                "PA template(s) {} were(was) added to kuberdock, but "
                "aren't (isn't) listed by '{} predefined-apps list'".
                format(", ".join(not_listed_names), command))

        # If all of them are listed, check that they are listed correctly
        for t in templates:
            _check_pa_template(listed_templates[t["template name"]],
                               origin=t.get("origin"))

    # Add several PAs templates to the catalog
    templates = [
        {"application name": "wordpress",
         "template name": "my pa 1",
         "origin": "kuberdock"},

        {"application name": "dokuwiki",
         "template name": "my pa 2"},

        {"application name": "drupal",
         "template name": "my pa 3"},
    ]
    for template in templates:
        cmd = "predefined-apps create "
        if "origin" in template:
            cmd += "--origin {} ".format(template["origin"])

        cmd += "--name '{}' -f {}".\
               format(template["template name"],
                      PREDEFINED_APPLICATION_FILES[template["application "
                                                            "name"]])
        cluster.kdctl(cmd)

    _check_list_output("kdctl")

    _check_list_output("kcli2")


@pipeline("PA_catalog", skip_reason="FIXME in AC-4743")
@hooks(setup=_clear_pa_catalog)
def test_update_pa_template_by_name(cluster):
    """Check that PA template can be updated.

    At first the dokuwiki PA template is created. Then it's updated by
    dpupal.yaml, and checked.

    """
    name = "my pa"
    _pa_create(cluster, name, f=PREDEFINED_APPLICATION_FILES["dokuwiki"])
    _pa_update(cluster, f=PREDEFINED_APPLICATION_FILES["drupal"], name=name)

    template = _pa_get(cluster, file_only=True, name=name)
    _, yaml, _ = cluster.ssh_exec("master", "cat {}".
                                  format(PREDEFINED_APPLICATION_FILES["drupal"]))
    assert_eq(template, yaml)


@pipeline("PA_catalog", skip_reason="FIXME in AC-4743")
@hooks(setup=_clear_pa_catalog)
def test_update_pa_template_by_id(cluster):
    """Check that PA template can be updated.

    At first the dokuwiki PA template is created. Then it's updated by
    dpupal.yaml, and checked.

    """
    name = "my pa"
    template = _pa_create(cluster, name,
                          f=PREDEFINED_APPLICATION_FILES["dokuwiki"])
    id_ = template["id"]
    _pa_update(cluster, f=PREDEFINED_APPLICATION_FILES["drupal"], id=id_)

    template = _pa_get(cluster, file_only=True, id=id_)
    _, yaml, _ = cluster.ssh_exec("master", "cat {}".
                                  format(PREDEFINED_APPLICATION_FILES["drupal"]))
    assert_eq(template, yaml)


@pipeline("PA_catalog", skip_reason="FIXME in AC-4743")
@hooks(setup=_clear_pa_catalog)
def test_validating_yaml_before_updating_pa_template(cluster):
    name = "my pa"
    _pa_create(cluster, name, f=PREDEFINED_APPLICATION_FILES["dokuwiki"])

    # Check that --validate flag prevents updating pa template by invalid yaml
    _pa_update(cluster, data="'some: invalid\nexpression'", validate=True,
               name=name)

    # Check that --validate flag allows updating pa template by valid yaml
    _, correct_yaml, _ = cluster.ssh_exec("master", "cat {}".
                                          format(PREDEFINED_APPLICATION_FILES
                                                 ["drupal"]))
    _pa_update(cluster, data=correct_yaml, validate=True, name=name)
    template = _pa_get(cluster, file_only=True, name=name)
    assert_eq(template, correct_yaml)


@pipeline("PA_catalog")
@hooks(setup=_clear_pa_catalog)
def test_add_and_run_pa(cluster):
    name = "dokuwiki.yaml"
    _pa_create(cluster, name, f=PREDEFINED_APPLICATION_FILES["dokuwiki"])
    pod = cluster.pods.create_pa(
        name, command="kdctl", owner="test_user", healthcheck=True,
        rnd_str="kdctl", wait_ports=True, wait_for_status=POD_STATUSES.running)

    pod.delete()


class InvalidTemplate(Exception):
    pass


class PATemplateNotInList(Exception):
    pass
