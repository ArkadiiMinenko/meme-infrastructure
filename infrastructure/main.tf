resource "proxmox_virtual_environment_vm" "k8s_nodes" {
  count     = 3
  name      = "k8s-node-${count.index + 1}"
  node_name = "pve"
  vm_id     = 200 + count.index

  clone {
    vm_id = 100
    full  = true
  }

  agent {
    enabled = true
  }

  cpu {
    cores = 2
    type  = "host"
  }

  memory {
    dedicated = 2048
  }

  disk {
    datastore_id = "local-lvm"
    interface    = "scsi0"
    size         = 20
    file_format  = "raw"
    iothread     = true
  }

  network_device {
    bridge = "vmbr0"
    model  = "virtio"
  }

  initialization {
    ip_config {
      ipv4 {
        address = "192.168.0.6${count.index + 1}/24"
        gateway = "192.168.0.1"
      }
    }
    
    user_account {
      username = "ubuntu"
      keys     = [file("tf-key.pub")]
    }
    
    dns {
      servers = ["1.1.1.1"]
    }
  }
  
  started = true
}

resource "local_file" "ansible_inventory" {
  content = <<EOT
[master]
${proxmox_virtual_environment_vm.k8s_nodes[0].initialization[0].ip_config[0].ipv4[0].address != "" ? element(split("/", proxmox_virtual_environment_vm.k8s_nodes[0].initialization[0].ip_config[0].ipv4[0].address), 0) : ""}

[workers]
%{ for i, vm in proxmox_virtual_environment_vm.k8s_nodes ~}
%{ if i > 0 ~}
${element(split("/", vm.initialization[0].ip_config[0].ipv4[0].address), 0)}
%{ endif ~}
%{ endfor ~}

[k8s_cluster:children]
master
workers

[k8s_cluster:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=~/.ssh/tf-key
ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
EOT
  filename = "inventory.ini"
}