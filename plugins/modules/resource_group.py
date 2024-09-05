#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: resource_group
version_added: 0.7.4
short_description: Manage Harness Resource Group
description:
  - Manage Harness Resource Groups.
author:
  - Justin McCormick (@karcadia)
options:
  identifier:
    description: Identifier of the Harness Resource Group.
    required: True
    type: str
  org:
    description: Identifier of the Harness Organization to which the Resource Group will belong.
    required: False
    type: str
  project:
    description: Identifier of the Harness Project to which the Resource Group will belong.
    required: False
    type: str
  state:
    description: Desired state of the Harness Resource Group.
    choices:
      - absent
      - present
    default: present
    type: str
  name:
    description: Name of the Harness Resource Group.
    required: False
    type: str
  tags:
    description: A dictionary of tags to add the Harness Resource Group.
    type: dict
  description:
    description: A description to apply to the Harness Resource Group.
    required: False
    type: str
  color:
    description: The hex color code to use for the Harness Resource Group.
    required: False
    type: str
  included_scope:
    description: Included scopes for the resources belonging to the Harness Resource Group.
    required: False
    type: list
  resource_filter:
    description: Specifies the actual resources present in the Harness Resource Group.
    required: False
    type: list
  include_all_resources:
    description: Boolean value for including all resources in the Harness Resource Group.
    required: False
    type: bool
"""

EXAMPLES = r"""
# Note: These examples do not set authentication details.

- name: Create a Harness Resource Group.
  karcadia.harness.resource_group:
    identifier: demo_resource_group
    org: my_demo_org

- name: Create a Harness Resource Group.
  karcadia.harness.resource_group:
    identifier: my_demo_resource_group
    org: my_demo_org
    name: my-demo-resource-group
    description: The Resource Group used for a Demo.
    state: present
    tags:
      purpose: demo

- name: Delete a Harness Resource Group.
  karcadia.harness.resource_group:
    identifier: demo_resource_group
    org: my_demo_org
    state: absent
"""

RETURN = r"""
resource_group:
  description: The resource group structure that was created.
  returned: when state is present
  type: dict
  suboptions:
    description:
      description: The description applied to the Harness Resource Group.
      type: str
    identifier:
      description: Identifier of the Harness Resource Group.
      type: str
    name:
      description: Name of the Harness Resource Group.
      type: str
    org:
      description: Identifier of the Harness Organization to which the Resource Group belongs.
      type: str
    project:
      description: Identifier of the Harness Project to which the Resource Group belongs.
      type: str
    tags:
      description: A dictionary of tags attached to the Harness Resource Group.
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
    else:
      harness_resp_dict = loads(harness_response.text)
      if harness_resp_dict['code'] == 'RESOURCE_NOT_FOUND_EXCEPTION':
        checked_and_absent = True
      else:
        msg = 'Harness response invalid or unexpected. Ensure your API Key is correct.\n'
        msg += harness_response.text
        module.fail_json(msg=msg)

    # Prepare the object with the required fields.
    pre_json_object = {
      "identifier": object_id,
      "name": object_name,
    }
    pjso = pre_json_object

    # Attach the org and project IDs as needed.
    if module.object_scope == 'project':
      pjso['orgIdentifier'] = org_id
      pjso['projectIdentifier'] = project_id
    elif module.object_scope == 'org':
      pjso['orgIdentifier'] = org_id

    # Add anything additional that was provided.
    if 'description' in module.params.keys():
      pjso['description'] = module.params['description']
    if 'color' in module.params.keys():
      pjso['color'] = module.params['color']
    if 'tags' in module.params.keys():
      pjso['tags'] = module.params['tags']
    if 'included_scope' in module.params.keys():
      pjso['included_scope'] = module.params['included_scope']
    if 'resource_filter' in module.params.keys():
      pjso['resource_filter'] = module.params['resource_filter']
    if 'include_all_resources' in module.params.keys():
      pjso['include_all_resources'] = module.params['include_all_resources']

    if checked_and_present:
      # Determine if the existing object needs to be updated.
      existing = loads(harness_response.text)
      needs_update = False
      if pjso['description'] and pjso['description'] != existing['description']:
        needs_update = True
        component = 'description'
      if pjso['included_scope'] and pjso['included_scope'] != existing['included_scope']:
        needs_update = True
        component = 'included_scope'
      if pjso['resource_filter'] and pjso['resource_filter'] != existing['resource_filter']:
        needs_update = True
        component = 'resource_filter'
      if pjso['include_all_resources'] and pjso['include_all_resources'] != existing['include_all_resources']:
        needs_update = True
        component = 'include_all_resources'
      if pjso['color'] and pjso['color'] != existing['color']:
        needs_update = True
        component = 'color'
      if pjso['tags'] and pjso['tags'] != existing['tags']:
        needs_update = True
        component = 'tags'
      if pjso['name'] != existing['name']:
        needs_update = True
        component = 'name'
      
      # Stop here if no updates are needed. Otherwise we'll use a PUT method to update the existing object.
      if needs_update:
        method = 'PUT'
        url = module.read_url
        if module.check_mode:
          # Return success with the object that we would have created.
          diff = {
            'before': existing,
            'after': pre_json_object
          }
          module.exit_json(changed=True, msg=f'{module.object_title} {object_id} has been updated.',
                           check_mode=True, resource_group=pre_json_object, updated=True, component_triggering_update=component, diff=diff)
      else:
        module.exit_json(changed=False, msg=f'{module.object_title} {object_id} is already present and in the desired state.')

    if checked_and_absent:
      if module.check_mode:
        # Return success with the object that we would have created.
        module.exit_json(changed=True, msg=f'{module.object_title} {object_id} has been created.',
                         check_mode=True, resource_group=pre_json_object[module.object_type])

      # We will use a POST method to create the missing object.
      method = 'POST'
      url = module.push_url

    # Push the object into Harness.
    create_object_resp = request(method, url, headers=module.headers, data=dumps(pre_json_object))

    # Interpret the API response.
    if method == 'PUT':
      actioned = 'updated'
      diff = {
        'before': existing,
        'after': pre_json_object
      }
      # Extract the object returned from the Harness API and return it with our successful module exit.
      object_resp_dict = loads(create_object_resp.text)
      module.exit_json(changed=True, msg=f'{module.object_title} {object_id} has been {actioned}.',
                       resource_group=object_resp_dict, updated=True, component_triggering_update=component, diff=diff)
    if method == 'POST':
      actioned = 'created'
      # Extract the object returned from the Harness API and return it with our successful module exit.
      object_resp_dict = loads(create_object_resp.text)['data']
      object_resp = object_resp_dict[module.object_type]
      module.exit_json(changed=True, msg=f'{module.object_title} {object_id} has been {actioned}.', resource_group=object_resp)
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
      harness_resp_dict = loads(harness_response.text)
      if harness_resp_dict['code'] == 'RESOURCE_NOT_FOUND_EXCEPTION':
        checked_and_absent = True
      else:
        msg = 'Harness response invalid or unexpected. Ensure your API Key is correct.\n'
        msg += harness_response.text
        module.fail_json(msg=msg)

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
          name=dict(type='str', required=False),
          identifier=dict(type='str', required=True, aliases=['id', 'resource_group_id']),
          org=dict(type='str', required=False, aliases=['org_id']),
          project=dict(type='str', required=False, aliases=['project_id']),
          state=dict(type='str', required=False, choices=['present', 'absent'], default='present'),
          api_key=dict(type='str', required=False),
          account_id=dict(type='str', required=False),
          description=dict(type='str', required=False, aliases=['desc']),
          color=dict(type='str', required=False),
          tags=dict(type='dict', required=False),
          included_scope=dict(type='list', required=False),
          resource_filter=dict(type='list', required=False),
          include_all_resources=dict(type='bool', required=False),
      ),
      supports_check_mode = True
    )

    # Set the object type for this module.
    module.object_type = 'resource-group'
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
    if module.object_scope == 'account':
      module.read_url = f'https://app.harness.io/v1/{module.object_type}s/{object_id}'
      module.push_url = f'https://app.harness.io/v1/{module.object_type}s'
    elif module.object_scope == 'org':
      module.read_url = f'https://app.harness.io/v1/orgs/{org_id}/{module.object_type}s/{object_id}'
      module.push_url = f'https://app.harness.io/v1/orgs/{org_id}/{module.object_type}s'
    elif module.object_scope == 'project':
      module.read_url = f'https://app.harness.io/v1/orgs/{org_id}/projects/{project_id}/{module.object_type}s/{object_id}'
      module.push_url = f'https://app.harness.io/v1/orgs/{org_id}/projects/{project_id}/{module.object_type}s'

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