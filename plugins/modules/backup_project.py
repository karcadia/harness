#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: backup_project
version_added: 0.1.2
short_description: Back up a Harness Project to a tarball
description:
  - Back up a Harness Project to a tarball.
author:
  - Justin McCormick (@karcadia)
options:
  identifier:
    description: Identifier of the Harness Project.
    required: True
    type: str
  org:
    description: Identifier of the Harness Organization to which the Project belongs.
    required: True
    type: str
  dest:
    description: Where to place the backup tarball file.
    required: False
    type: str
"""

EXAMPLES = r"""
- name: Backup a Harness Project.
  karcadia.harness.project:
    identifier: demo_project
    org: my_demo_org

- name: Backup a Harness Project.
  karcadia.harness.project:
    identifier: demo_project
    org: my_demo_org
    dest: /tmp/backups/harness-backup.tar.gz

- name: Backup a Harness Project.
  karcadia.harness.project:
    identifier: demo_project
    org: my_demo_org
  environment:
    HARNESS_ACCOUNT_ID: abc123
    HARNESS_API_KEY: abc123
"""

RETURN = r"""
msg:
  description: Project has been backed up. With destination provided.
  type: str
"""

# Internal Imports
from ansible.module_utils.basic import AnsibleModule

# Stdlib Imports
from os import getenv, mkdir
from os.path import isdir
from shutil import rmtree
from json import dumps, loads
from yaml import dump
from uuid import uuid4
from tarfile import open as tar_open

# External Imports
from requests import request

def backup_object(module):
    # Pull in the module parameters.
    object_id  = module.params["identifier"]
    org_id     = module.params["org"]

    # Prepare to hit the Harness API.
    url = f'https://app.harness.io/v1/orgs/{org_id}/{module.object_type}s/{object_id}'
    
    # Start with some assumptions.
    checked_and_absent = False
    checked_and_present = False

    # Hit the Harness API and pull our object by ID.
    # https://apidocs.harness.io/tag/Org-Project#operation/get-org-scoped-project
    harness_response = request("GET", url, headers=module.headers)
    if harness_response.status_code == 404:
      checked_and_absent = True
    elif harness_response.status_code == 200:
      checked_and_present = True
    else:
      module.fail_json(msg='Harness response invalid or unexpected. Ensure your API Key is correct.')

    if checked_and_absent:
      module.fail_json(msg=f'{module.object_title} {object_id} does not exist.')

    dest = module.params["dest"]
    if not dest:
      dest = 'ansible_harness_project_backup_' + object_id + '.tar.gz'

    # Handle check mode by pretending we are done now.
    if module.check_mode:
      module.exit_json(changed=True, msg=f'{module.object_title} {object_id} has been backed up to {dest}.', check_mode=True)

    # We can probably condense all these functions quite a bit by categorizing them into 3 API types.
    # One of those things that is easier now that we have each object's API interactions categorized.

    # Hand off to each function to fetch:
    # default settings (not gathered at this time)
    # services
    # environments
    # environment groups
    # infrastructure definitions
    # connectors
    # delegates
    # secrets
    # file store (not gathered at this time)
    # templates
    # variables
    # slo downtime (not gathered at this time)
    # monitored services (not gathered at this time)
    # users
    # user groups
    # service accounts
    # resource groups
    # roles

    # Prepare the workdir with a random name.
    rand_str = str(uuid4())
    module.work_dir = '.ansible-tmp-' + rand_str
    mkdir(module.work_dir)

    # Gather the files and details for all of the object types.
    fetch_services(module, org_id, object_id)
    fetch_environments(module, org_id, object_id)
    # Infrastructures get fetched from within fetch_environments.
    fetch_environment_groups(module, org_id, object_id)
    fetch_connectors(module, org_id, object_id)
    fetch_delegates(module, org_id, object_id)
    fetch_secrets(module, org_id, object_id)
    fetch_templates(module, org_id, object_id)
    fetch_variables(module, org_id, object_id)
    fetch_users(module, org_id, object_id)
    fetch_user_groups(module, org_id, object_id)
    fetch_service_accounts(module, org_id, object_id)
    fetch_resource_groups(module, org_id, object_id)
    fetch_roles(module, org_id, object_id)

    # Generate the tarball now that all the files are in place.
    with tar_open(dest, 'w:gz') as tar:
      tar_name = dest.split('.')[0]
      tar.add(module.work_dir, arcname=tar_name)

    # Cleanup our work dir that we have the tarball.
    rmtree(module.work_dir)

    module.exit_json(changed=True, msg=f'{module.object_title} {object_id} has been backed up to {dest}.')

def fetch_services(module, org_id, object_id):
  # Fetch services for project.
  page = 0
  page_limit = 20
  url = f'https://app.harness.io/v1/orgs/{org_id}/projects/{object_id}/services?page={page}&limit={page_limit}&sort=name&order=ASC'
  service_list_resp = request("GET", url, headers=module.headers)

  # Interpret the API response.
  if service_list_resp.status_code == 200:
    # Check if we got all the items on the first call.
    service_list = loads(service_list_resp.text)
    resp_headers = service_list_resp.headers
    page_number = int(resp_headers['X-Page-Number'])
    items_so_far = (page_number + 1) * page_limit
    total_elements = int(resp_headers['X-Total-Elements'])
    while items_so_far < total_elements:
      # Keep calling until we have everything.
      page = page_number + 1
      url = f'https://app.harness.io/v1/orgs/{org_id}/projects/{object_id}/services?page={page}&limit={page_limit}&sort=name&order=ASC'
      service_list_resp = request("GET", url, headers=module.headers)
      service_list.extend(loads(service_list_resp.text))
      resp_headers = service_list_resp.headers
      page_number = int(resp_headers['X-Page-Number'])
      items_so_far = (page_number + 1) * page_limit
      total_elements = int(resp_headers['X-Total-Elements'])
  else:
    # Try to extract the status_code to return with our failure.
    status_code = str(service_list_resp.status_code)
    msg=[]
    msg.append(f'Harness Service List Response was unexpected. Status Code: {status_code}')
    module.fail_json(msg=msg)

  # Now that we have all of our services, write them out to files in our workdir.
  mkdir(module.work_dir + '/services')
  for service_dict in service_list:
    service = service_dict['service']
    service_id = service['identifier']
    mkdir(module.work_dir + '/services/' + service_id)
    service_filename = module.work_dir + '/services/' + service_id + '/' + service_id + '.yaml'
    with open(service_filename, 'w') as file_writer:
      file_writer.write(service['yaml'])

def fetch_environments(module, org_id, project_id):
  # Fetch environments for project.
  page = 0
  page_limit = 20
  account_id = module.headers['Harness-Account']
  url = f'https://app.harness.io/ng/api/environmentsV2?page={page}&size={page_limit}&accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}&sort=name'
  env_list_resp = request("GET", url, headers=module.headers)

  # Interpret the API response.
  if env_list_resp.status_code == 200:
    # Check if we got all the items on the first call.
    env_list = loads(env_list_resp.text)['data']['content']
    resp_headers = env_list_resp.headers
    while 'Content-Length' not in resp_headers.keys():
      # Keep calling until we have everything.
      page += 1
      url = f'https://app.harness.io/ng/api/environmentsV2?page={page}&size={page_limit}&accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}&sort=name'
      env_list_resp = request("GET", url, headers=module.headers)
      env_list.extend(loads(env_list_resp.text)['data']['content'])
      resp_headers = env_list_resp.headers
  else:
    # Try to extract the status_code to return with our failure.
    status_code = str(env_list_resp.status_code)
    msg=[]
    msg.append(f'Harness Environment List Response was unexpected. Status Code: {status_code}')
    module.fail_json(msg=msg)

  # Now that we have all of our environments, write them out to files in our workdir.
  mkdir(module.work_dir + '/environments')
  for env_dict in env_list:
    env = env_dict['environment']
    env_id = env['identifier']
    mkdir(module.work_dir + '/environments/' + env_id)
    # Each infra has to fetched at the environment level.
    fetch_infras(module, org_id, project_id, env_id)
    env_filename = module.work_dir + '/environments/' + env_id + '/' + env_id + '.yaml'
    with open(env_filename, 'w') as file_writer:
      file_writer.write(env['yaml'])

def fetch_environment_groups(module, org_id, project_id):
  # Fetch environment groups for project.
  page = 0
  page_limit = 20
  account_id = module.headers['Harness-Account']
  url = f'https://app.harness.io/ng/api/environmentGroup/list?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}&page={page}&size={page_limit}&sort=name'
  env_group_list_resp = request("POST", url, headers=module.headers)

  # Interpret the API response.
  if env_group_list_resp.status_code == 200:
    # Check if we got all the items on the first call.
    env_group_list = loads(env_group_list_resp.text)['data']['content']
    resp_headers = env_group_list_resp.headers
    while 'Content-Length' not in resp_headers.keys():
      # Keep calling until we have everything.
      page += 1
      url = f'https://app.harness.io/ng/api/environmentGroup/list?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}&page={page}&size={page_limit}&sort=name'
      env_group_list_resp = request("POST", url, headers=module.headers)
      env_group_list.extend(loads(env_group_list_resp.text)['data']['content'])
      resp_headers = env_group_list_resp.headers
  else:
    # Try to extract the status_code to return with our failure.
    status_code = str(env_group_list_resp.status_code)
    msg=[]
    msg.append(f'Harness Environment Group List Response was unexpected. Status Code: {status_code}')
    msg.append(f'{env_group_list_resp.text}')
    module.fail_json(msg=msg)

  # Now that we have all of our environment groups, write them out to files in our workdir.
  mkdir(module.work_dir + '/environment_groups')
  for env_dict in env_group_list:
    env = env_dict['envGroup']
    env_id = env['identifier']
    mkdir(module.work_dir + '/environment_groups/' + env_id)
    env_filename = module.work_dir + '/environment_groups/' + env_id + '/' + env_id + '.yaml'
    with open(env_filename, 'w') as file_writer:
      file_writer.write(env['yaml'])

def fetch_infras(module, org_id, project_id, env_id):
  # Fetch infrastructures for project.
  page = 0
  page_limit = 20
  account_id = module.headers['Harness-Account']
  url = f'https://app.harness.io/ng/api/infrastructures?page={page}&size={page_limit}&accountIdentifier={account_id}'
  url += f'&orgIdentifier={org_id}&projectIdentifier={project_id}&environmentIdentifier={env_id}&sort=name'
  infra_list_resp = request("GET", url, headers=module.headers)

  # Interpret the API response.
  if infra_list_resp.status_code == 200:
    # Check if we got all the items on the first call.
    infra_list = loads(infra_list_resp.text)['data']['content']
    resp_headers = infra_list_resp.headers
    while 'Content-Length' not in resp_headers.keys():
      # Keep calling until we have everything.
      page += 1
      url = f'https://app.harness.io/ng/api/infrastructures?page={page}&size={page_limit}&accountIdentifier={account_id}'
      url += f'&orgIdentifier={org_id}&projectIdentifier={project_id}&environmentIdentifier={env_id}&sort=name'
      infra_list_resp = request("GET", url, headers=module.headers)
      infra_list.extend(loads(infra_list_resp.text)['data']['content'])
      resp_headers = infra_list_resp.headers
  else:
    # Try to extract the status_code to return with our failure.
    status_code = str(infra_list_resp.status_code)
    msg=[]
    msg.append(f'Harness Infrastructure List Response was unexpected. Status Code: {status_code}')
    msg.append(f'{infra_list_resp.text}')
    module.fail_json(msg=msg)

  # Now that we have all of our infrastructures, write them out to files in our workdir.
  for infra_dict in infra_list:
    infra = infra_dict['infrastructure']
    infra_id = infra['identifier']
    if not isdir(module.work_dir + '/environments/' + env_id):
      mkdir(module.work_dir + '/environments/' + env_id)
    if not isdir(module.work_dir + '/environments/' + env_id + '/infrastructures'):
      mkdir(module.work_dir + '/environments/' + env_id + '/infrastructures/')
    mkdir(module.work_dir + '/environments/' + env_id + '/infrastructures/' + infra_id)
    infra_filename = module.work_dir + '/environments/' + env_id + '/infrastructures/' + infra_id + '/' + infra_id + '.yaml'
    with open(infra_filename, 'w') as file_writer:
      file_writer.write(infra['yaml'])

def fetch_connectors(module, org_id, project_id):
  # Fetch connectors for project.
  page = 0
  page_limit = 20
  account_id = module.headers['Harness-Account']
  url = f'https://app.harness.io/ng/api/connectors/listV2?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}&includeAllConnectorsAvailableAtScope=false&onlyFavorites=false&pageIndex={page}&pageSize={page_limit}'
  connector_list_resp = request("POST", url, headers=module.headers)

  # Interpret the API response.
  if connector_list_resp.status_code == 200:
    # Check if we got all the items on the first call.
    connector_list = loads(connector_list_resp.text)['data']['content']
    resp_headers = connector_list_resp.headers
    while 'Content-Length' not in resp_headers.keys():
      # Keep calling until we have everything.
      page += 1
      url = f'https://app.harness.io/ng/api/connectors/listV2?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}&includeAllConnectorsAvailableAtScope=false&onlyFavorites=false&pageIndex={page}&pageSize={page_limit}'
      connector_list_resp = request("POST", url, headers=module.headers)
      connector_list.extend(loads(connector_list_resp.text)['data']['content'])
      resp_headers = connector_list_resp.headers
  else:
    # Try to extract the status_code to return with our failure.
    status_code = str(connector_list_resp.status_code)
    msg=[]
    msg.append(f'Harness Infrastructure List Response was unexpected. Status Code: {status_code}')
    msg.append(f'{connector_list_resp.text}')
    module.fail_json(msg=msg)

  # Now that we have all of our connectors, write them out to files in our workdir.
  mkdir(module.work_dir + '/connectors')
  for connector_dict in connector_list:
    connector = {}
    connector['connector'] = connector_dict['connector']
    yaml_content = dump(connector)
    connector_id = connector['connector']['identifier']
    mkdir(module.work_dir + '/connectors/' + connector_id)
    connector_filename = module.work_dir + '/connectors/' + connector_id + '/' + connector_id + '.yaml'
    with open(connector_filename, 'w') as file_writer:
      file_writer.write(yaml_content)

def fetch_delegates(module, org_id, project_id):
  # Fetch connectors for project.
  account_id = module.headers['Harness-Account']
  url = f'https://app.harness.io/ng/api/delegate-setup/listDelegates?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}'
  data = {}
  data['filterType'] = 'Delegate'
  delegate_list_resp = request("POST", url, headers=module.headers, data=dumps(data))

  # Interpret the API response.
  if delegate_list_resp.status_code == 200:
    # Check if we got all the items on the first call.
    delegate_list = loads(delegate_list_resp.text)['resource']
    resp_headers = delegate_list_resp.headers
    # I don't see any documentation for pagination on this one. Maybe it always returns everything?
  else:
    # Try to extract the status_code to return with our failure.
    status_code = str(delegate_list_resp.status_code)
    msg=[]
    msg.append(f'Harness Delegate Response was unexpected. Status Code: {status_code}')
    msg.append(f'{delegate_list_resp.text}')
    module.fail_json(msg=msg)

  # Now that we have all of our delegates, write them out to files in our workdir.
  mkdir(module.work_dir + '/delegates')
  for delegate_dict in delegate_list:
    yaml_content = dump(delegate_dict)
    delegate_name = delegate_dict['name']
    mkdir(module.work_dir + '/delegates/' + delegate_name)
    delegate_filename = module.work_dir + '/delegates/' + delegate_name + '/' + delegate_name + '.yaml'
    with open(delegate_filename, 'w') as file_writer:
      file_writer.write(yaml_content)

def fetch_secrets(module, org_id, project_id):
  # Fetch secrets for project.
  page = 0
  page_limit = 20
  url = f'https://app.harness.io/v1/orgs/{org_id}/projects/{project_id}/secrets?page={page}&limit={page_limit}&sort=name&order=ASC'
  secrets_list_resp = request("GET", url, headers=module.headers)

  # Interpret the API response.
  if secrets_list_resp.status_code == 200:
    # Bail out if the returned list is empty.
    if secrets_list_resp.text == "[]":
      return
    # Check if we got all the items on the first call.
    secrets_list = loads(secrets_list_resp.text)
    resp_headers = secrets_list_resp.headers
    while 'Content-Length' not in resp_headers.keys():
      # Keep calling until we have everything.
      page += 1
      url = f'https://app.harness.io/v1/orgs/{org_id}/projects/{project_id}/secrets?page={page}&limit={page_limit}&sort=name&order=ASC'
      secrets_list_resp = request("GET", url, headers=module.headers)
      secrets_list.extend(loads(secrets_list_resp.text))
      resp_headers = secrets_list_resp.headers
  else:
    # Try to extract the status_code to return with our failure.
    status_code = str(secrets_list_resp.status_code)
    msg=[]
    msg.append(f'Harness Secrets List Response was unexpected. Status Code: {status_code}')
    msg.append(f'{secrets_list_resp.text}')
    module.fail_json(msg=msg)

  mkdir(module.work_dir + '/secrets')
  # Now that we have all of our secrets, write them out to files in our workdir.
  for secret_dict in secrets_list:
    secret = secret_dict['secret']
    secret_id = secret['identifier']
    mkdir(module.work_dir + '/secrets/' + secret_id)
    secret_filename = module.work_dir + '/secrets/' + secret_id + '/' + secret_id + '.yaml'
    yaml_content = dump(secret_dict)
    with open(secret_filename, 'w') as file_writer:
      file_writer.write(yaml_content)

def fetch_templates(module, org_id, project_id):
  # Fetch templates for project.
  page = 0
  page_limit = 20
  url = f'https://app.harness.io/v1/orgs/{org_id}/projects/{project_id}/templates?page={page}&limit={page_limit}&sort=identifier&order=ASC'
  templates_list_resp = request("GET", url, headers=module.headers)

  # Interpret the API response.
  if templates_list_resp.status_code == 200:
    # Bail out if the returned list is empty.
    if templates_list_resp.text == "[]":
      return
    # Check if we got all the items on the first call.
    templates_list = loads(templates_list_resp.text)
    resp_headers = templates_list_resp.headers
    while 'Content-Length' not in resp_headers.keys():
      # Keep calling until we have everything.
      page += 1
      url = f'https://app.harness.io/v1/orgs/{org_id}/projects/{project_id}/templates?page={page}&limit={page_limit}&sort=identifier&order=ASC'
      templates_list_resp = request("GET", url, headers=module.headers)
      templates_list.extend(loads(templates_list_resp.text))
      resp_headers = templates_list_resp.headers
  else:
    # Try to extract the status_code to return with our failure.
    status_code = str(templates_list_resp.status_code)
    msg=[]
    msg.append(f'Harness Secrets List Response was unexpected. Status Code: {status_code}')
    msg.append(f'{templates_list_resp.text}')
    module.fail_json(msg=msg)

  mkdir(module.work_dir + '/templates')
  # Now that we have all of our templates, write them out to files in our workdir.
  for template_dict in templates_list:
    template_id = template_dict['identifier']
    mkdir(module.work_dir + '/templates/' + template_id)
    template_filename = module.work_dir + '/templates/' + template_id + '/' + template_id + '.yaml'
    yaml_content = dump(template_dict)
    with open(template_filename, 'w') as file_writer:
      file_writer.write(yaml_content)

def fetch_variables(module, org_id, project_id):
  # Fetch variables for project.
  page = 0
  page_limit = 20
  account_id = module.headers['Harness-Account']
  url = f'https://app.harness.io/ng/api/variables?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}'
  url += f'&includeVariablesFromEverySubScope=false&pageIndex={page}&pageSize={page_limit}'
  variables_list_resp = request("GET", url, headers=module.headers)

  # Interpret the API response.
  if variables_list_resp.status_code == 200:
    # Bail out if the returned list is empty.
    if variables_list_resp.text == "[]":
      return
    # Check if we got all the items on the first call.
    variables_list = loads(variables_list_resp.text)['data']['content']
    resp_headers = variables_list_resp.headers
    while 'Content-Length' not in resp_headers.keys():
      # Keep calling until we have everything.
      page += 1
      url = f'https://app.harness.io/ng/api/variables?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}'
      url += f'&includeVariablesFromEverySubScope=false&pageIndex={page}&pageSize={page_limit}'
      variables_list_resp = request("GET", url, headers=module.headers)
      variables_list.extend(loads(variables_list_resp.text)['data']['content'])
      resp_headers = variables_list_resp.headers
  else:
    # Try to extract the status_code to return with our failure.
    status_code = str(variables_list_resp.status_code)
    msg=[]
    msg.append(f'Harness Secrets List Response was unexpected. Status Code: {status_code}')
    msg.append(f'{variables_list_resp.text}')
    module.fail_json(msg=msg)

  mkdir(module.work_dir + '/variables')
  # Now that we have all of our variables, write them out to files in our workdir.
  for variable_dict in variables_list:
    variable = variable_dict['variable']
    variable_id = variable['identifier']
    mkdir(module.work_dir + '/variables/' + variable_id)
    variable_filename = module.work_dir + '/variables/' + variable_id + '/' + variable_id + '.yaml'
    yaml_content = dump(variable_dict)
    with open(variable_filename, 'w') as file_writer:
      file_writer.write(yaml_content)

def fetch_users(module, org_id, project_id):
  # Fetch users for project.
  page = 0
  page_limit = 20
  account_id = module.headers['Harness-Account']
  url = f'https://app.harness.io/ng/api/user/aggregate?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}'
  url += f'&pageIndex={page}&pageSize={page_limit}'
  users_list_resp = request("POST", url, headers=module.headers, data={})

  # Interpret the API response.
  if users_list_resp.status_code == 200:
    # Bail out if the returned list is empty.
    if users_list_resp.text == "[]":
      return
    # Check if we got all the items on the first call.
    users_list = loads(users_list_resp.text)['data']['content']
    resp_headers = users_list_resp.headers
    while 'Content-Length' not in resp_headers.keys():
      # Keep calling until we have everything.
      page += 1
      url = f'https://app.harness.io/ng/api/user/aggregate?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}'
      url += f'&pageIndex={page}&pageSize={page_limit}'
      users_list_resp = request("POST", url, headers=module.headers, data={})
      users_list.extend(loads(users_list_resp.text)['data']['content'])
      resp_headers = users_list_resp.headers
  else:
    # Try to extract the status_code to return with our failure.
    status_code = str(users_list_resp.status_code)
    msg=[]
    msg.append(f'Harness Users List Response was unexpected. Status Code: {status_code}')
    msg.append(f'{users_list_resp.text}')
    module.fail_json(msg=msg)

  mkdir(module.work_dir + '/users')
  # Now that we have all of our users, write them out to files in our workdir.
  for user_dict in users_list:
    user = user_dict['user']
    user_name = user['name']
    mkdir(module.work_dir + '/users/' + user_name)
    user_filename = module.work_dir + '/users/' + user_name + '/' + user_name + '.yaml'
    yaml_content = dump(user_dict)
    with open(user_filename, 'w') as file_writer:
      file_writer.write(yaml_content)

def fetch_user_groups(module, org_id, project_id):
  # Fetch user groups for project.
  page = 0
  page_limit = 20
  account_id = module.headers['Harness-Account']
  url = f'https://app.harness.io/ng/api/user-groups?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}'
  url += f'&pageIndex={page}&pageSize={page_limit}'
  user_groups_list_resp = request("GET", url, headers=module.headers)

  # Interpret the API response.
  if user_groups_list_resp.status_code == 200:
    # Bail out if the returned list is empty.
    if user_groups_list_resp.text == "[]":
      return
    # Check if we got all the items on the first call.
    user_groups_list = loads(user_groups_list_resp.text)['data']['content']
    resp_headers = user_groups_list_resp.headers
    while 'Content-Length' not in resp_headers.keys():
      # Keep calling until we have everything.
      page += 1
      url = f'https://app.harness.io/ng/api/user-groups?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}'
      url += f'&pageIndex={page}&pageSize={page_limit}'
      user_groups_list_resp = request("GET", url, headers=module.headers)
      user_groups_list.extend(loads(user_groups_list_resp.text)['data']['content'])
      resp_headers = user_groups_list_resp.headers
  else:
    # Try to extract the status_code to return with our failure.
    status_code = str(user_groups_list_resp.status_code)
    msg=[]
    msg.append(f'Harness User Groups List Response was unexpected. Status Code: {status_code}')
    msg.append(f'{user_groups_list_resp.text}')
    module.fail_json(msg=msg)

  mkdir(module.work_dir + '/user_groups')
  # Now that we have all of our users, write them out to files in our workdir.
  for user_group_dict in user_groups_list:
    user_group_id = user_group_dict['identifier']
    mkdir(module.work_dir + '/user_groups/' + user_group_id)
    user_group_filename = module.work_dir + '/user_groups/' + user_group_id + '/' + user_group_id + '.yaml'
    yaml_content = dump(user_group_dict)
    with open(user_group_filename, 'w') as file_writer:
      file_writer.write(yaml_content)

def fetch_service_accounts(module, org_id, project_id):
  # Fetch service accounts for project.
  page = 0
  page_limit = 20
  account_id = module.headers['Harness-Account']
  url = f'https://app.harness.io/ng/api/serviceaccount/aggregate?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}'
  url += f'&pageIndex={page}&pageSize={page_limit}'
  service_account_list_resp = request("GET", url, headers=module.headers)

  # Interpret the API response.
  if service_account_list_resp.status_code == 200:
    # Bail out if the returned list is empty.
    if service_account_list_resp.text == "[]":
      return
    # Check if we got all the items on the first call.
    service_account_list = loads(service_account_list_resp.text)['data']['content']
    resp_headers = service_account_list_resp.headers
    while 'Content-Length' not in resp_headers.keys():
      # Keep calling until we have everything.
      page += 1
      url = f'https://app.harness.io/ng/api/serviceaccount/aggregate?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}'
      url += f'&pageIndex={page}&pageSize={page_limit}'
      service_account_list_resp = request("GET", url, headers=module.headers)
      service_account_list.extend(loads(service_account_list_resp.text)['data']['content'])
      resp_headers = service_account_list_resp.headers
  else:
    # Try to extract the status_code to return with our failure.
    status_code = str(service_account_list_resp.status_code)
    msg=[]
    msg.append(f'Harness Service Account List Response was unexpected. Status Code: {status_code}')
    msg.append(f'{service_account_list_resp.text}')
    module.fail_json(msg=msg)

  mkdir(module.work_dir + '/service_accounts')
  # Now that we have all of our users, write them out to files in our workdir.
  for service_account_dict in service_account_list:
    service_account = service_account_dict['serviceAccount']
    service_account_id = service_account['identifier']
    mkdir(module.work_dir + '/service_accounts/' + service_account_id)
    service_account_filename = module.work_dir + '/service_accounts/' + service_account_id + '/' + service_account_id + '.yaml'
    yaml_content = dump(service_account_dict)
    with open(service_account_filename, 'w') as file_writer:
      file_writer.write(yaml_content)

def fetch_resource_groups(module, org_id, project_id):
  # Fetch resource groups for project.
  page = 0
  page_limit = 20
  account_id = module.headers['Harness-Account']
  url = f'https://app.harness.io/v1/orgs/{org_id}/projects/{project_id}/resource-groups?page={page}&limit={page_limit}&sort=identifier&order=ASC'
  resource_group_list_resp = request("GET", url, headers=module.headers)

  # Interpret the API response.
  if resource_group_list_resp.status_code == 200:
    # Bail out if the returned list is empty.
    if resource_group_list_resp.text == "[]":
      return
    # Check if we got all the items on the first call.
    resource_group_list = loads(resource_group_list_resp.text)
    resp_headers = resource_group_list_resp.headers
    while 'Content-Length' not in resp_headers.keys():
      # Keep calling until we have everything.
      page += 1
      url = f'https://app.harness.io/v1/orgs/{org_id}/projects/{project_id}/resource-groups?page={page}&limit={page_limit}&sort=identifier&order=ASC'
      resource_group_list_resp = request("GET", url, headers=module.headers)
      resource_group_list.extend(loads(resource_group_list_resp.text))
      resp_headers = resource_group_list_resp.headers
  else:
    # Try to extract the status_code to return with our failure.
    status_code = str(resource_group_list_resp.status_code)
    msg=[]
    msg.append(f'Harness Resource Group List Response was unexpected. Status Code: {status_code}')
    msg.append(f'{resource_group_list_resp.text}')
    module.fail_json(msg=msg)

  mkdir(module.work_dir + '/resource_groups')
  # Now that we have all of our users, write them out to files in our workdir.
  for resource_group_dict in resource_group_list:
    resource_group_id = resource_group_dict['identifier']
    mkdir(module.work_dir + '/resource_groups/' + resource_group_id)
    resource_group_filename = module.work_dir + '/resource_groups/' + resource_group_id + '/' + resource_group_id + '.yaml'
    yaml_content = dump(resource_group_dict)
    with open(resource_group_filename, 'w') as file_writer:
      file_writer.write(yaml_content)

def fetch_roles(module, org_id, project_id):
  # Fetch resource groups for project.
  page = 0
  page_limit = 20
  account_id = module.headers['Harness-Account']
  url = f'https://app.harness.io/v1/orgs/{org_id}/projects/{project_id}/roles?page={page}&limit={page_limit}&sort=identifier&order=ASC'
  role_list_resp = request("GET", url, headers=module.headers)

  # Interpret the API response.
  if role_list_resp.status_code == 200:
    # Bail out if the returned list is empty.
    if role_list_resp.text == "[]":
      return
    # Check if we got all the items on the first call.
    role_list = loads(role_list_resp.text)
    resp_headers = role_list_resp.headers
    while 'Content-Length' not in resp_headers.keys():
      # Keep calling until we have everything.
      page += 1
      url = f'https://app.harness.io/v1/orgs/{org_id}/projects/{project_id}/roles?page={page}&limit={page_limit}&sort=identifier&order=ASC'
      role_list_resp = request("GET", url, headers=module.headers)
      role_list.extend(loads(role_list_resp.text))
      resp_headers = role_list_resp.headers
  else:
    # Try to extract the status_code to return with our failure.
    status_code = str(role_list_resp.status_code)
    msg=[]
    msg.append(f'Harness Role List Response was unexpected. Status Code: {status_code}')
    msg.append(f'{role_list_resp.text}')
    module.fail_json(msg=msg)

  mkdir(module.work_dir + '/roles')
  # Now that we have all of our users, write them out to files in our workdir.
  for role_dict in role_list:
    role_id = role_dict['identifier']
    mkdir(module.work_dir + '/roles/' + role_id)
    role_filename = module.work_dir + '/roles/' + role_id + '/' + role_id + '.yaml'
    yaml_content = dump(role_dict)
    with open(role_filename, 'w') as file_writer:
      file_writer.write(yaml_content)

def main():
    # Set the object type for this module.
    object_type = 'project'

    # Initialize the module and specify the argument spec.
    module = AnsibleModule(
      argument_spec = dict(
          name=dict(type='str', required=False),
          identifier=dict(type='str', required=True, aliases=['id', 'project_id']),
          org=dict(type='str', required=True, aliases=['org_id']),
          api_key=dict(type='str', required=False),
          account_id=dict(type='str', required=False),
          dest=dict(type='str', required=False),
      ),
      supports_check_mode = True
    )

    # Set the object type for this module.
    module.object_type = 'project'
    module.object_title = module.object_type.title()

    # Catch and fail when we were given an ID with a dash in it.
    identifier = module.params['identifier']
    org = module.params['org']
    if '-' in identifier or '-' in org:
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

    # Call the backup function.
    backup_object(module)

if __name__ == "__main__":
    main()