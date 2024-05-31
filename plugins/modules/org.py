#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: org
version_added: 0.1.0
short_description: Manage Harness Org
description:
  - Manage Harness Orgs.
author:
  - Justin McCormick (@karcadia)
options:
  identifier:
    description: Identifier of the Harness Org.
    required: True
    type: str
  state:
    description: Desired state of the Harness Org.
    choices:
      - absent
      - present
    default: present
    required: False
    type: str
  name:
    description: Name of the Harness Org.
    required: False
    type: str
  tags:
    description: A dictionary of tags to add the Harness Org.
    type: dict
  description:
    description: A description to apply to the Harness Org.
    required: False
    type: str
"""

EXAMPLES = r"""
- name: Create a Harness Org.
  karcadia.harness.org:
    identifier: demo

- name: Create a Harness Org.
  karcadia.harness.org:
    identifier: demo
    account_id: abc123
    api_key: abc123

- name: Create a Harness Org.
  karcadia.harness.org:
    identifier: demo
  environment:
    HARNESS_ACCOUNT_ID: abc123
    HARNESS_API_KEY: abc123

- name: Create a Harness Org.
  karcadia.harness.org:
    identifier: my_demo_org
    name: my-demo-org
    description: The Org used for a Demo.
    state: present
    tags:
      purpose: demo

- name: Delete a Harness Org.
  karcadia.harness.org:
    identifier: demo
    state: absent
"""

RETURN = r"""
org:
  description: The org structure that was created.
  returned: when state is present
  type: dict
  suboptions:
    description:
      description: The description applied to the Harness Org.
      type: str
    identifier:
      description: Identifier of the Harness Org.
      type: str
    modules:
      description: A list of modules that are enabled for the Harness Org.
      type: list
      elements: str
    name:
      description: Name of the Harness Org.
      type: str
    tags:
      description: A dictionary of tags attached to the Harness Org.
      type: dict
"""

# Internal Imports
from ansible.module_utils.basic import AnsibleModule

# Stdlib Imports
from os import getenv
from json import dumps

# External Imports
from requests import request

def ensure_present(module):
    # Pull in the module parameters.
    org_id   = module.params["identifier"]
    org_name = module.params["name"]

    # Catch and fail when we were given an ID with a dash in it.
    if '-' in org_id:
      module.fail_json(msg='Harness Identifiers may not contain dashes.')

    # Use the same name as ID if name was not provided.
    if not org_name:
      org_name = org_id
    
    # Start with some assumptions.
    checked_and_absent = False
    checked_and_present = False

    # Hit the Harness API and pull our Organization by ID.
    # https://apidocs.harness.io/tag/Organization#operation/get-organization
    harness_response = request("GET", module.read_url, headers=module.headers)
    if harness_response.status_code == 404:
      checked_and_absent = True
    elif harness_response.status_code == 200:
      checked_and_present = True
    elif harness_response.status_code == 400:
      module.fail_json(msg='Harness response invalid or unexpected. Ensure your API Key is correct and you are licensed for this feature.')
    else:
      module.fail_json(msg='Harness response invalid or unexpected. Ensure your API Key is correct.')

    # Prepare the Org object with the required fields.
    pre_json_object = {
      module.object_type: {
        "identifier": org_id,
        "name": org_name
      }
    }

    # Add anything additional that was provided.
    if 'description' in module.params.keys():
      pre_json_object[module.object_type]['description'] = module.params['description']
    if 'tags' in module.params.keys():
      pre_json_object[module.object_type]['tags'] = module.params['tags']

    if checked_and_present:
      module.exit_json(changed=False, msg=f'Org {org_id} is already present.')

    if checked_and_present:
      # Determine if the existing object needs to be updated.
      existing = loads(harness_response.text)
      needs_update = False
      if pre_json_object[module.object_type]['description'] and pre_json_object[module.object_type]['description'] != existing[module.object_type]['description']:
        needs_update = True
        component = 'description'
      if pre_json_object[module.object_type]['tags'] and pre_json_object[module.object_type]['tags'] != existing[module.object_type]['tags']:
        needs_update = True
        component = 'tags'
      if pre_json_object[module.object_type]['name'] != existing[module.object_type]['name']:
        needs_update = True
        component = 'name'
      
      # Stop here if no updates are needed. Otherwise we'll use a PUT method to update the existing object.
      if needs_update:
        method = 'PUT'
        url = module.read_url
        if module.check_mode:
          # Return success with the object that we would have created.
          module.exit_json(changed=True, msg=f'{module.object_title} {org_id} has been updated.', check_mode=True, org=pre_json_object, updated=True)
      else:
        module.exit_json(changed=False, msg=f'{module.object_title} {org_id} is already present and in the desired state.')

    if checked_and_absent:
      if module.check_mode:
        # Return the Org object that we would have created.
        module.exit_json(changed=True, msg=f'Org {org_id} has been created.', org=pre_json_org)

      # We will use a POST method to create the missing object.
      method = 'POST'
      url = module.push_url

    # Push the Organization object into Harness.
    # https://apidocs.harness.io/tag/Organization#operation/create-organization
    create_object_resp = request(method, url, headers=module.headers, data=dumps(pre_json_org))
    if create_object_resp.status_code == 200:
      actioned = 'updated'
      # Extract the object returned from the Harness API and return it with our successful module exit.
      object_resp_dict = loads(create_object_resp.text)
      module.exit_json(changed=True, msg=f'{module.object_title} {object_id} has been {actioned}.', project=object_resp_dict, updated=True, component_triggering_update=component)
    if create_object_resp.status_code == 201:
      actioned = 'created'
      # Extract the object returned from the Harness API and return it with our successful module exit.
      object_resp_dict = loads(create_object_resp.text)
      module.exit_json(changed=True, msg=f'Org {org_id} has been {actioned}.', org=object_resp_dict)
    else:
      msg = 'Harness Org creation has failed.\n'
      msg += f'{create_object_resp.text}'
      module.fail_json(msg=f'{msg}')

def ensure_absent(module):
    # Pull in the module parameters.
    org_id = module.params["identifier"]
    
    # Start with some assumptions.
    checked_and_absent = False
    checked_and_present = False

    # Hit the Harness API and pull our Organization by ID.
    # https://apidocs.harness.io/tag/Organization#operation/get-organization
    harness_response = request("GET", module.read_url, headers=module.headers)
    if harness_response.status_code == 404:
      checked_and_absent = True
    elif harness_response.status_code == 200:
      checked_and_present = True
    elif harness_response.status_code == 400:
      module.fail_json(msg='Harness response invalid or unexpected. Ensure your API Key is correct and you are licensed for this feature.')
    else:
      module.fail_json(msg='Harness response invalid or unexpected. Ensure your API Key is correct.')

    if checked_and_absent:
      module.exit_json(changed=False, msg=f'Org {org_id} is already absent.')

    if checked_and_present:
      if module.check_mode:
        module.exit_json(changed=True, msg=f'Org {org_id} has been deleted.')

      # Delete the Organization.
      # https://apidocs.harness.io/tag/Organization#operation/delete-organization
      delete_org_resp = request("DELETE", module.read_url, headers=module.headers)
      if delete_org_resp.status_code == 200:
        module.exit_json(changed=True, msg=f'Org {org_id} has been deleted.')
      else:
        status_code = str(delete_org_resp.status_code)
        msg = 'Harness Org Delete Response was unexpected. Org may or may not be deleted.\n'
        msg += f'{status_code}'
        module.fail_json(msg=f'{msg}')

def main():
    module = AnsibleModule(
      argument_spec = dict(
          name=dict(type='str', required=False),
          identifier=dict(type='str', required=True, aliases=['id', 'org_id']),
          state=dict(type='str', required=False, choices=['present', 'absent'], default='present'),
          api_key=dict(type='str', required=False),
          account_id=dict(type='str', required=False),
          description=dict(type='str', required=False, aliases=['desc']),
          tags=dict(type='dict', required=False),
      ),
      supports_check_mode = True
    )

    # Set the object type for this module.
    module.object_type = 'org'
    module.object_title = module.object_type.title()

    # Catch and fail when we were given an ID with a dash in it.
    org_id = module.params["identifier"]
    if '-' in org_id:
      module.fail_json(msg='Harness Identifiers may not contain dashes.')

    # Pull the environment variables if they were provided.
    env_harness_api_key = getenv('HARNESS_API_KEY')
    env_harness_account_id = getenv('HARNESS_ACCOUNT_ID')

    # Catch and fail if we don't have the auth information.
    api_key = module.params['api_key']
    account_id = module.params['account_id']
    if not api_key and not env_harness_api_key:
      module.fail_json(msg='Must provide api_key to the module or HARNESS_API_KEY to the environment.')
    if not account_id and not env_harness_account_id:
      module.fail_json(msg='Must provide account_id to the module or HARNESS_ACCOUNT_ID to the environment.')

    # If we were not provided auth information to the module, pull it from the environment.
    if api_key:
      module.api_key = api_key
    else:
      module.api_key = env_harness_api_key
    if account_id:
      module.account_id = account_id
    else:
      module.account_id = env_harness_account_id

    # Prepare to hit the Harness API.
    headers = {}
    headers['x-api-key'] = module.api_key
    headers['Harness-Account'] = module.account_id
    headers['Content-Type'] = 'application/json'
    module.headers = headers
    module.read_url = f'https://app.harness.io/v1/orgs/{org_id}'
    module.push_url = 'https://app.harness.io/v1/orgs'

    # Run the appropriate function based on the state requested.
    state = module.params['state']
    if state == "present":
        ensure_present(module)
    elif state == "absent":
        ensure_absent(module)
    else:
        module.fail_json(msg="Invalid value for state. Supported values are 'present' and 'absent'.")

if __name__ == "__main__":
    main()
