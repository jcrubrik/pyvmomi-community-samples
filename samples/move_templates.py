#!/usr/bin/env python3

"""
Python program for listing the VMs on an ESX / vCenter host
"""

import re
from pyVmomi import vmodl, vim
from tools import cli, service_instance
import urllib3

urllib3.disable_warnings() 

import ssl

try:
  _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
# Legacy Python that doesn't verify HTTPS certificates by default
  pass
else:
# Handle target environment that doesn't support HTTPS verification
  ssl._create_default_https_context = _create_unverified_https_context
#
# exmaple: 
#   python3 ./move_templates.py -s eng-vcenter5.colo.rubrik.com -u podmaker@rubrik-lab.com -p Nm4aGOFygqMB1P4o  -f ESX_ -d cloudon
#
def wait_for_task(task):
    """ wait for a vCenter task to finish """
    task_done = False
    while not task_done:
        if task.info.state == 'success':
            return task.info.result

        if task.info.state == 'error':
            print("there was an error")
            print(task.info.error)
            task_done = True


def print_vm_info(virtual_machine):
    """
    Print information for a particular virtual machine or recurse into a
    folder with depth protection
    """
    summary = virtual_machine.summary
    print("Name       : ", summary.config.name)
    print("Template   : ", summary.config.template)
    print("Path       : ", summary.config.vmPathName)
    print("Guest      : ", summary.config.guestFullName)
    print("Instance UUID : ", summary.config.instanceUuid)
    print("Bios UUID     : ", summary.config.uuid)
    if virtual_machine.datastore is None:
        print('No datastore info in VM.')
    else:
        print("Datastore     : ", virtual_machine.datastore[0].summary.name)

def print_datastore_info(datastore):
    """
    Print information for a particular virtual machine or recurse into a
    folder with depth protection
    """
    summary = datastore.summary
    print("Datastore Name  : ", summary.name)
    print("Datastore Type: ", summary.type)

def move_template(vm, resource_pool, datastore):
    """
    Move template to target datastore
    """
    # move template
    if vm.datastore[0].summary.name != datastore.summary.name:
        if vm.summary.config.template:
            print("Convert to VM " + vm.summary.config.name)
            vm.MarkAsVirtualMachine(pool=resource_pool)

        # create the relocation spec
        print("Move VM from " + vm.datastore[0].summary.name + " to " + datastore.summary.name)
        relospec = vim.vm.RelocateSpec()
        relospec.datastore = datastore
        task = vm.RelocateVM_Task(spec = relospec)
        wait_for_task(task)
    
    if not vm.summary.config.template:
        print("Convert to Template " + vm.summary.config.name)
        vm.MarkAsTemplate()
     
    
def main():
    """
    Simple command-line program for listing the virtual machines on a system.
    """
    parser = cli.Parser()
    parser.add_custom_argument('-f', '--find', required=False,
                               action='store', help='String to match VM names')
    parser.add_custom_argument('-d', '--datastore', required=False,
                               action='store', help='String to match datastore name')
    args = parser.get_args()
    si = service_instance.connect(args)

    try:
        content = si.RetrieveContent()

        container = content.rootFolder  # starting point to look into
        recursive = True  # whether we should look into it recursively
        resource_pool_view = content.viewManager.CreateContainerView(
            container, [vim.ResourcePool], recursive)

        children = resource_pool_view.view
        for child in children:
            if child.summary.name == "JackieVMs":
                resource_pool = child        

        if resource_pool is None:
            print("Resource Pool not found!!!\n")
            return
            
        view_type = [vim.Datastore]  # object types to look for
        datastore_view = content.viewManager.CreateContainerView(
            container, view_type, recursive)
        children = datastore_view.view

        if args.datastore is not None:
            pat = re.compile(args.datastore, re.IGNORECASE)
        for child in children:
            if args.datastore is None:
                print_datastore_info(child)
            else:
                if pat.search(child.summary.name) is not None:
                    print_datastore_info(child)
                    datastore = child
        
        view_type = [vim.VirtualMachine]  # object types to look for
        recursive = True  # whether we should look into it recursively
        container_view = content.viewManager.CreateContainerView(
            container, view_type, recursive)

        children = container_view.view

        if args.find is not None:
            pat = re.compile(args.find, re.IGNORECASE)
        for child in children:
            if args.find is None:
                print_vm_info(child)
            else:
                if pat.search(child.summary.config.name) is not None:
                    print_vm_info(child)
                    move_template(child, resource_pool, datastore)

    except vmodl.MethodFault as error:
        print("Caught vmodl fault : " + error.msg)
        return -1

    return 0


# Start program
if __name__ == "__main__":
    main()
