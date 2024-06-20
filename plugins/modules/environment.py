#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: environment
version_added: 0.2.4
short_description: Manage Harness Environment
description:
  - Manage Harness Environments.
author:
  - Justin McCormick (@karcadia)
options:
  identifier:
    description: Identifier of the Harness Environment.
    required: False
    type: str
  org:
    description: Identifier of the Harness Organization to which the Environment will belong.
    required: False
    type: str
  project:
    description: Identifier of the Harness Organization to which the Environment will belong.
    required: False
    type: str
  state:
    description: Desired state of the Harness Environment.
    choices:
      - absent
      - present
    default: present
    type: str
  name:
    description: Name of the Harness Environment.
    required: False
    type: str
  tags:
    description: A dictionary of tags to add the Harness Environment.
    type: dict
  description:
    description: A description to apply to the Harness Environment.
    required: False
    type: str
  spec:
    description: 
    required: 
    type: 
"""

EXAMPLES = r"""
# Note: These examples do not set authentication details.

- name: Create a Harness Environment.
  karcadia.harness.environment:
    identifier: demo_environment
    org: my_demo_org

- name: Create a Harness Environment.
  karcadia.harness.environment:
    identifier: my_demo_environment
    org: my_demo_org
    name: my-demo-environment
    description: The Environment used for a Demo.
    state: present
    tags:
      purpose: demo

- name: Delete a Harness Environment.
  karcadia.harness.environment:
    identifier: demo_environment
    org: my_demo_org
    state: absent
"""

RETURN = r"""
environment:
  description: The environment structure that was created.
  returned: when state is present
  type: dict
  suboptions:
    description:
      description: The description applied to the Harness Environment.
      type: str
    identifier:
      description: Identifier of the Harness Environment.
      type: str
    name:
      description: Name of the Harness Environment.
      type: str
    org:
      description: Identifier of the Harness Organization to which the Environment belongs.
      type: str
    project:
      description: Identifier of the Harness Project to which the Environment belongs.
      type: str
    tags:
      description: A dictionary of tags attached to the Harness Environment.
      type: dict
"""

# Internal Imports
from ansible.module_utils.basic import AnsibleModule

# Stdlib Imports
from os import getenv
from json import dumps, loads

# External Imports
from requests import request

def ensure_present(module):
    # Pull in the module parameters.
    object_id   = module.params["identifier"]
    object_name = module.params["name"]
    org_id      = module.params["org"]
    project_id  = module.params["project"]
    env_type    = module.params["type"]

    # Use the same name as ID if name was not provided.
    if not object_name:
      object_name = object_id
    
    # Start with some assumptions.
    checked_and_absent = False
    checked_and_present = False

    # Hit the Harness API and pull our object by ID.
    harness_response = request("GET", module.read_url, headers=module.headers)
    if harness_response.status_code == 404:
      checked_and_absent = True
    elif harness_response.status_code == 200:
      checked_and_present = True
    elif harness_response.status_code == 400:
      harness_response_dict = loads(harness_response.text)
      harness_response_code = harness_response_dict['code']
      if harness_response_code == 'RESOURCE_NOT_FOUND_EXCEPTION':
        checked_and_absent = True
      else:
        module.fail_json(msg=harness_response_code)
    else:
      module.fail_json(msg='Harness response invalid or unexpected. Ensure your API Key is correct.')

    # Prepare the object with the required fields.
    pre_json_object = {
      "identifier": object_id,
      "name": object_name,
      "type": env_type,
    }

    # Attach the org and project IDs as needed.
    if module.object_scope == 'project':
      pre_json_object['orgIdentifier'] = org_id
      pre_json_object['projectIdentifier'] = project_id
    elif module.object_scope == 'org':
      pre_json_object['orgIdentifier'] = org_id

    # Add anything additional that was provided.
    if 'description' in module.params.keys():
      pre_json_object['description'] = module.params['description']
    if 'tags' in module.params.keys():
      pre_json_object['tags'] = module.params['tags']
    if 'color' in module.params.keys():
      pre_json_object['color'] = module.params['color']
    if 'yaml' in module.params.keys():
      pre_json_object['yaml'] = module.params['yaml']

    if checked_and_present:
      # Determine if the existing object needs to be updated.
      existing = loads(harness_response.text)['data'][module.object_type]
      needs_update = False
      if pre_json_object['description'] \
        and pre_json_object['description'] != existing['description']:
          needs_update = True
          component = 'description'
      if pre_json_object['tags'] \
        and pre_json_object['tags'] != existing['tags']:
          needs_update = True
          component = 'tags'
      if pre_json_object['color'] \
        and pre_json_object['color'] != existing['color']:
          needs_update = True
          component = 'color'
      if pre_json_object['yaml'] \
        and pre_json_object['yaml'] != existing['yaml']:
          needs_update = True
          component = 'yaml'
      if pre_json_object['name'] != existing['name']:
        needs_update = True
        component = 'name'
      
      # Stop here if no updates are needed. Otherwise we'll use a PUT method to update the existing object.
      if needs_update:
        method = 'PUT'
        url = module.push_url
        if module.check_mode:
          # Return success with the object that we would have created.
          module.exit_json(changed=True, msg=f'{module.object_title} {object_id} has been updated.', check_mode=True,
                           environment=pre_json_object, updated=True, component_triggering_update=component)
      else:
        module.exit_json(changed=False, msg=f'{module.object_title} {object_id} is already present and in the desired state.')

    if checked_and_absent:
      if module.check_mode:
        # Return success with the object that we would have created.
        module.exit_json(changed=True, msg=f'{module.object_title} {object_id} has been created.',
                         check_mode=True, environment=pre_json_object)

      # We will use a POST method to create the missing object.
      method = 'POST'
      url = module.push_url

    # Push the object into Harness.
    create_object_resp = request(method, url, headers=module.headers, data=dumps(pre_json_object))

    # Interpret the API response.
    if create_object_resp.status_code == 200:
      # Extract the object returned from the Harness API and return it with our successful module exit.
      object_resp_dict = loads(create_object_resp.text)
      if method == 'POST':
        actioned = 'created'
        msg = f'{module.object_title} {object_id} has been {actioned}.'
        module.exit_json(changed=True, msg=msg, environment=object_resp_dict)
      if method == 'PUT':
        actioned = 'updated'
        msg = f'{module.object_title} {object_id} has been {actioned}.'
        diff = {
          'before': existing,
          'after': pre_json_object
        }
        module.exit_json(changed=True, msg=msg, diff=diff, environment=object_resp_dict, component_triggering_update=component)
    else:
      # Try to extract the status_code to return with our failure.
      status_code = str(create_object_resp.status_code)
      msg=[]
      msg.append(f'Harness {module.object_title} creation has failed. Status Code: {status_code}')
      if type(create_object_resp) is dict():
        error_dict = eval(create_object_resp.text)
        error_details = error_dict['details']
        msg.append(f'{error_details}')
      else:
        msg.append(create_object_resp.text)
      module.fail_json(msg=msg)

def ensure_absent(module):
    # Pull in the module parameters.
    object_id  = module.params["identifier"]
    org_id     = module.params["org"]
    project_id = module.params["project"]

    # Start with some assumptions.
    checked_and_absent = False
    checked_and_present = False

    # Hit the Harness API and pull our object by ID.
    harness_response = request("GET", module.read_url, headers=module.headers)
    if harness_response.status_code == 404:
      checked_and_absent = True
    elif harness_response.status_code == 200:
      checked_and_present = True
    else:
      module.fail_json(msg='Harness response invalid or unexpected. Ensure your API Key is correct.')

    if checked_and_absent:
      module.exit_json(changed=False, msg=f'{module.object_title} {object_id} is already absent.')

    if checked_and_present:
      if module.check_mode:
        # For check mode we just pretend we deleted it.
        module.exit_json(changed=True, msg=f'{module.object_title} {object_id} has been deleted.', check_mode=True)

      # Delete the Object.
      delete_object_resp = request("DELETE", module.read_url, headers=module.headers)

      # Interpret the API response.
      if delete_object_resp.status_code == 200:
        # Return a success message reporting that we have deleted this object.
        module.exit_json(changed=True, msg=f'{module.object_title} {object_id} has been deleted.')
      else:
        # Try to extract the status_code to return with our failure.
        status_code = str(delete_object_resp.status_code)
        msg=[]
        msg.append(f'Harness {module.object_title} Delete Response was unexpected. {module.object_title} may or may not be deleted. Status Code: {status_code}')
        if type(delete_object_resp) is dict():
          error_dict = eval(delete_object_resp.text)
          error_details = error_dict['details']
          msg.append(f'{error_details}')
        else:
          msg.append(delete_object_resp.text)
        module.fail_json(msg=msg)

def main():
    # Initialize the module and specify the argument spec.
    module = AnsibleModule(
      argument_spec = dict(
          name=dict(type='str'),
          identifier=dict(type='str', required=True, aliases=['id', 'env_id']),
          org=dict(type='str', aliases=['org_id']),
          project=dict(type='str', aliases=['project_id']),
          state=dict(type='str', choices=['present', 'absent'], default='present'),
          api_key=dict(type='str'),
          account_id=dict(type='str'),
          description=dict(type='str', aliases=['desc']),
          type=dict(type='str'),
          color=dict(type='str'),
          tags=dict(type='dict'),
          yaml=dict(type='str'),
      ),
      supports_check_mode = True,
      required_if = [
        ('state', 'present', ('type',))
      ]
    )

    # Set the object type for this module.
    module.object_type = 'environment'
    module.object_title = module.object_type.title()

    # Catch and fail when we were given an ID with a dash in it.
    object_id = module.params['identifier']
    org_id = module.params['org']
    project_id = module.params['project']
    if '-' in object_id:
      module.fail_json(msg='Harness Identifiers may not contain dashes.')
    if org_id and '-' in org_id:
      module.fail_json(msg='Harness Identifiers may not contain dashes.')
    if project_id and '-' in project_id:
      module.fail_json(msg='Harness Identifiers may not contain dashes.')
    if project_id and not org_id:
      module.fail_json(msg='Org ID must be provided when project is provided.')

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

    # Determine the scope of our object.
    if org_id and project_id:
      module.object_scope = 'project'
    elif org_id:
      module.object_scope = 'org'
    else:
      module.object_scope = 'account'

    # Prepare the Harness API URLs for this module.
    module.push_url = f'https://app.harness.io/ng/api/environmentsV2?accountIdentifier={module.account_id}'
    module.read_url = f'https://app.harness.io/ng/api/environmentsV2/{object_id}?accountIdentifier={module.account_id}&deleted=false'
    if module.object_scope == 'org':
      module.read_url += f'&orgIdentifier={org_id}'
    elif module.object_scope == 'project':
      module.read_url += f'&orgIdentifier={org_id}&projectIdentifier={project_id}'

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