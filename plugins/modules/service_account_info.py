#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: service_account_info
version_added: 0.8.1
short_description: Retrieve service account information from Harness for the given scope.
description:
  - Retrieve information for Harness Service Accounts.
  - Can be used at account, org, or project scope.
author:
  - Justin McCormick (@karcadia)
options:
  org:
    description: Identifier of the Harness Organization from which the service account list should be pulled.
    required: False
    type: str
  project:
    description: Identifier of the Harness Project from which the service account list should be pulled.
    required: False
    type: str
"""

EXAMPLES = r"""
- name: List Harness account-level service accounts.
  karcadia.harness.service_account_info:

- name: List Harness org-level service accounts.
  karcadia.harness.service_account_info:
    org: my_demo_org

- name: List Harness project-level service accounts.
  karcadia.harness.service_account_info:
    org: my_demo_org
    project: my_demo_project
  register: service_account_list

- name: List Harness project-level service accounts.
  karcadia.harness.service_account_info:
    org: my_demo_org
    project: my_demo_project
  register: service_account_list
  environment:
    HARNESS_ACCOUNT_ID: abc123
    HARNESS_API_KEY: abc123
"""

RETURN = r"""
service_accounts:
  description: List of service accounts found in scope.
  type: list
"""

# Internal Imports
from ansible.module_utils.basic import AnsibleModule

# Stdlib Imports
from os import getenv
from json import dumps, loads
from yaml import dump

# External Imports
from requests import request

def fetch_service_accounts(module, org_id, project_id):
  # Fetch service accounts for given scope.
  page = 0
  page_limit = 20
  url = module.url
#  url += f'&limit={page_limit}'
#  url_without_page = url
#  url += f'&page={page}'
  with open("debug.txt", "w") as fw:
    fw.write(url)
  service_account_resp = request("GET", url, headers=module.headers)

  # Interpret the API response.
  if service_account_resp.status_code == 200:
    # Check if we got all the items on the first call.
    service_account_list = loads(service_account_resp.text)
#    resp_headers = service_account_resp.headers
#    page_number = int(resp_headers['X-Page-Number'])
#    items_so_far = (page_number + 1) * page_limit
#    total_elements = int(resp_headers['X-Total-Elements'])
#    while items_so_far < total_elements:
      # Keep calling until we have everything.
#      page += 1
#      url = url_without_page
#      url += f'&page={page}'
#      service_account_resp = request("GET", url, headers=module.headers)
#      service_account_list.extend(loads(service_account_resp.text))
#      resp_headers = service_account_resp.headers
#      page_number = int(resp_headers['X-Page-Number'])
#      items_so_far = (page_number + 1) * page_limit
#      total_elements = int(resp_headers['X-Total-Elements'])
  else:
    # Try to extract the status_code to return with our failure.
    status_code = str(service_account_resp.status_code)
    msg=[]
    msg.append(f'Harness Service Account List Response was unexpected. Status Code: {status_code}')
    msg.append(service_account_resp.text)
    module.fail_json(msg=msg)

  module.exit_json(changed=False, service_accounts=service_account_list)

def main():
    # Initialize the module and specify the argument spec.
    module = AnsibleModule(
      argument_spec = dict(
          org=dict(type='str', required=False, aliases=['org_id']),
          project=dict(type='str', required=False, aliases=['project_id']),
          api_key=dict(type='str', required=False),
          account_id=dict(type='str', required=False),
      ),
      supports_check_mode = True
    )

    # Set the object type for this module.
    module.object_type = 'serviceaccount'
    module.object_title = module.object_type.title()

    # Catch and fail when we were given an ID with a dash in it.
    org_id = module.params['org']
    project_id = module.params['project']
    if org_id and '-' in org_id:
      module.fail_json(msg='Harness Identifiers may not contain dashes.')
    if project_id and '-' in project_id:
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
    module.url = f'https://app.harness.io/ng/api/{module.object_type}?accountIdentifier={module.account_id}'
    if module.object_scope == 'org':
      module.url += f'orgIdentifer={org_id}'
    elif module.object_scope == 'project':
      module.url += f'orgIdentifer={org_id}&projectIdentifier={project_id}'

    # Call the backup function.
    fetch_service_accounts(module, org_id, project_id)

if __name__ == "__main__":
    main()