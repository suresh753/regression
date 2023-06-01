# Owner -- durgarao.gambali@blaize.com
import argparse
import glob, os, json, sys
import pandas as pd
import subprocess
import time
import datetime
import timeit
import yaml
import numpy as np
from termcolor import colored
from collections import OrderedDict
import re


def osubproc(cmd, skip_exit=0, myprint=print):
    try:
        p1 = subprocess.Popen([cmd],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              shell=True)
        p1.wait()
        rc = p1.returncode
        if rc == 0 or rc == 256:
            out = str(p1.stdout.read().decode('ascii', 'ignore'))
            if out != '':
                myprint(out)
            return rc, out
        else:
            err = str(p1.stderr.read().decode('ascii', 'ignore'))
            if err != '':
                myprint(err)
            #loc='/home/%s/%s' % (self.test_params['gsp_uname'], self.test_params['mount_point'].split('/')[-1])
            if err.find('mv: cannot') != -1 or err.find(
                    'cannot connect to X server'
            ) != -1 or err.find('umount:') != -1 or err.find(
                    'rmmod: ERROR: Module blaize is not currently loaded'
            ) != -1 or err == '' or err.find('dpkg: warning: ignoring'):
                myprint('Ignoring the failures')
            else:
                myprint("Issue in System call=%s" % cmd)
                if skip_exit == 0:
                    sys.exit(1)
            return rc, err
    except Exception as e:
        sys.exit("Issue in System call=%s \nError message=%s" % (cmd, e))


def print_log(self, msg):
    ts = time.time()
    st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    if msg.find('Testing Stats for ') == -1:
        self.console_log(msg)
    self.fp.write(st + ' ' + msg + '\n')


def osubproc_communicate(cmd):
    p1 = subprocess.Popen([cmd],
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          shell=True)
    out, err = p1.communicate()
    rc = p1.returncode
    return rc, out.decode('ascii', 'ignore'), err.decode('ascii', 'ignore')


def osubproc_nocheck(cmd, myprint=print):
    try:
        p1 = subprocess.Popen([cmd],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              shell=True)
        p1.wait()
        rc = p1.returncode
        out = str(p1.stdout.read().decode('ascii', 'ignore'))
        err = str(p1.stderr.read().decode('ascii', 'ignore'))
        if err == '' and out != '':
            myprint(out)
        elif err != '':
            myprint(err)
        return rc, out, err
    except Exception as e:
        sys.exit("Issue in System call=%s \nError message=%s" % (cmd, e))


def osubproc_chkopt(cmd, nodisp=0, myprint=print):
    out = 'output_failed'
    try:
        out = subprocess.check_output(cmd,
                                      shell=True).decode('ascii', 'ignore')
        if nodisp == 0 and out != '':
            myprint(out)
    except Exception as e:
        myprint(e)
        myprint("Issue in executing command=%s" % cmd)
        out = 'output_failed'
    return out


def ochdir(cmd):
    os.chdir(cmd)


def is_file_exist(filePath):
    if not os.path.exists(filePath):
        sys.exit("The file %s does not exist!" % filePath)
    return True


def compare_ref_vs_current(local_reference, network_name, field, current,
                           variance):
    if network_name in local_reference and field in local_reference[
            network_name]:
        flt_ref = float(local_reference[network_name][field])
        flt_cur = float(current)
        display_color = 'white'
        success = True
        if flt_cur / flt_ref > 1 + (variance / 100):
            display_color = "green"
        if flt_cur / flt_ref < 1 - (variance / 100):
            display_color = "red"
            success = False
        return (success, "{:.2f}:{}".format(flt_ref,colored("{:.2f}:{:.1f}%".format(flt_cur, 100 * (flt_cur / flt_ref)),display_color)))
    else:
        return (True, "{:.2f}".format(current))


def parse_arguments(self):
    parser = argparse.ArgumentParser(
        description='Networks Regression script - Dev')
    parser.add_argument(
        "-n",
        "--network",
        help=
        "--network optional <network-name/network-names(list of networks seperated by space)>",
        required=False,
        default='all')
    parser.add_argument("-c",
                        "--config",
                        help="global configuration file of type json",
                        required=False,
                        default=self.config_file)
    parser.add_argument("-d",
                        "--datatype",
                        help="network data type",
                        type=str,
                        required=False,
                        default=None)
    parser.add_argument("-t", 
                        "--variant",
                        help="network variant type",
                        type=str,
                        required=False,
                        default=None)
    self.args = parser.parse_args()
    if is_file_exist(self.args.config):
        self.config_file = self.args.config


def get_network_dump(self):
    ochdir(os.path.expanduser('~/nfs_validation/repos/customer_networks'))
    res = glob.glob('*')
    data = {}
    data['networks'] = []
    for inp in res:
        data['networks'].append({'name': '%s' % inp})
    ochdir(self.cmd)
    with open(self.network_metadata_file, 'w') as fp:
        json.dump(data, fp)


def read_network_dump(self):
    if is_file_exist(self.network_metadata_file):
        try:
            with open(self.network_metadata_file, 'r') as fp:
                self.networks_data = json.load(fp)
        except Exception as e:
            print(e)
            sys.exit("Issue while parsing network metadata file=%s" %
                     self.network_metadata_file)

        for inp in self.networks_data['networks']:
            self.supported_networks[inp['name']] = OrderedDict({
                'network_name':
                inp['name'].upper(),
                'siExec':
                'FAILED',
                'softExec':
                'FAILED',
                'siSoftMatch':
                'FAILED',
                'performance':
                '-1',
                'randomness':
                'YES',
                'streamPerfWithWrap':
                '-1',
                'streamPerfWoWrap':
                '-1',
                'funcWithWrap':
                'FAILED',
                'funcWoWrap':
                'FAILED',
                'isHanging':
                'NO',
                'result':
                'PASSED'
            })
            net_params = self.test_params.copy()
            net_params.update(inp)
            if not 'network_variant_type' in inp:
                inp['network_variant_type'] = 'sgraph_mframe'
            if not 'app' in inp:
                inp['app'] = inp['name'] + '_' + inp[
                    'network_variant_type']
            if not 'duplicate' in inp:
                inp['duplicate'] = False
            if not 'broken' in inp:
                inp['broken'] = False
            if not 'slow' in inp:
                inp['slow'] = False
            if not 'extended' in inp:
                inp['extended'] = True
            if not 'variance' in inp:
                inp['variance'] = 0.7
            if not 'prefertype' in inp:
                inp['prefertype'] = 2
            if not 'framework' in inp:
                inp['framework'] = 'pytorch'
            if not 'data_type' in inp:
                inp['data_type'] = 'int8'
            net_params.update(inp)
            del net_params['name']
            self.supported_networks[inp['name']]['parameters'] = net_params


def mount_apps(self):
    self.nfs_location = self.test_params['nfs_mount_point']
    if os.path.ismount(self.nfs_location):
        self.console_log("Datasets are already mounted in %s" %
                         self.nfs_location)
    else:
        osubproc('sudo mkdir -p %s' % self.nfs_location)
        self.console_log("\n Mounting dataset : %s \n" %
                         self.test_params['nfs_details'])
        osubproc('sudo mount -t nfs %s %s' %
                 (self.test_params['nfs_details'], self.nfs_location))
        if os.path.ismount(self.nfs_location):
            self.console_log("Successfully Mounted Dataset")
        else:
            sys.exit(
                "Unable to mount datasets, There is an issue with the script")


def initialize_parameters(self):
    self.check_env()
    self.parse_arguments()
    # load config file parameters
    try:
        with open(self.config_file, 'r') as fp:
            self.test_params = json.load(fp)
    except Exception as e:
        print(e)
        sys.exit("Issue while parsing Config file=%s" % self.config_file)

    if self.test_params['network_metadata_file']:
        self.network_metadata_file = os.path.expandvars(
            self.test_params['network_metadata_file'])

    self.test_params['run_path'] = os.path.expanduser(
        self.test_params['run_path'])

    self.bkp_srv_loc = self.test_params['bkp_srv_loc']
    ip = osubproc_chkopt('hostname -I')
    if ip == "output_failed":
        sys.exit("Issue in getting IP of the machine=\"hosnetwork_name -I\"")
    self.test_params['gsp_ip'] = ip.split(' ')[0]

    self.nfs_mount_point = self.test_params['nfs_mount_point']

    self.read_network_dump()
    self.network = self.args.network.lower()
    if self.network != 'all':
        self.network = self.network.split()
        self.network = [x for x in self.network if x != ' ']
        for inp in self.network:
            if inp not in self.supported_networks.keys():
                print("Usage: python3 %s -n/--name <network-name>" %
                      sys.argv[0])
                sys.exit("List of supported networks =%s" %
                         self.supported_networks.keys())

    self.local_reference = {}
    if is_file_exist(self.test_params['local_reference_file']):
        try:
            with open(self.test_params['local_reference_file'], 'r') as fp:
                self.local_reference = yaml.load(fp, Loader=yaml.FullLoader)
        except Exception as e:
            print(e)
            print("Failed to load local reference file")
            self.local_reference = {}
    self.mount_apps()


def check_env(self):
    for inp in self.sdk_env:
        if os.getenv(inp) is None:
            sys.exit(
                "Script requires the following environment variables to set\n%s"
                % self.sdk_env)

def copy_app_from_to_bkp_srv(self, src_path, dst_path, ip, mode):
    if mode == 'put':
        self.console_log(
            'Copying %s from (%s) to BKP Server(%s) %s' %
            (src_path, ip, self.test_params['bkp_srv_ip'], dst_path))
    else:
        self.console_log(
            'Copying %s from BKP Server(%s) to %s %s' %
            (src_path, self.test_params['bkp_srv_ip'], ip, dst_path))
    try:
        osubproc("chmod 600 %s/bmt_key" % sys.path[0])
        (rc, out) = osubproc(
            'rsync -a --delete -e "ssh -i %s/bmt_key" %s@%s:%s %s' %
            (sys.path[0], self.test_params['bkp_srv_uname'],
             self.test_params['bkp_srv_ip'], src_path, dst_path))
        if rc != 0:
            return False
    except Exception as e:
        print(e)
        return False
    return True

def connect_paramiko(self, ip, uname, passwd):
    try:
        ssh_client = SSHClient()
        ssh_client.set_missing_host_key_policy(AutoAddPolicy())
        ssh_client.connect(hostname=ip,
                           username=uname,
                           password=passwd,
                           allow_agent=False,
                           look_for_keys=False)
        return ssh_client
    except:
        sys.exit("Unable to ssh to that machine")

def copy_app_from_remote_to_local(self, network_name):
    self.test_params['run_path'] = os.path.expanduser(
        self.test_params['run_path'])
    net_params = self.supported_networks[network_name]['parameters']
    if 'pipeline' in net_params['network_variant_type']:
        network_name = network_name.replace("_pipeline", '')
    if net_params['network_variant_type'] == 'pipeline':
        network_name = network_name.replace("_customer", '')
    remote_network_path = 'network_apps_netdeploy2004' + '/' + net_params[
            'framework'] + '/' + net_params[
                'network_variant_type'] + '/' + network_name + '/' + self.gold_app_name
    self.test_params['nfs_mount_point'] = self.nfs_location + '/' + remote_network_path
    self.test_params['bkp_srv_loc'] = self.bkp_srv_loc + '/' + remote_network_path
    ochdir('%s' % (self.test_params['run_path']))
    bkp_name = net_params['app']
    bkp_glob = glob.glob("%s*" % bkp_name.replace("-", "[-_]"))
    if len(bkp_glob) == 1:
        if bkp_name != bkp_glob[0]:
            print("different %s %s" % (bkp_name, bkp_glob))
        bkp_name = bkp_glob[0]
    if not os.path.isdir(bkp_name) or int(
            self.test_params['copy_latest_app']) == 1:
        self.console_log(
            "\n\n***************Copying Gold app for network %s***************\n"
            % network_name)
        app_dest_path = '%s/%s' % (os.getcwd(), bkp_name)

        if self.test_params['use_ssh_copy']:
            src = '%s/%s' % (self.test_params['bkp_srv_loc'], bkp_name)
            gold_res = self.copy_app_from_to_bkp_srv(src,
                                                     self.test_params['run_path'],
                                                     self.test_params['gsp_ip'],
                                                     'get')
        else:
            src = '%s/%s' % (self.test_params['nfs_mount_point'], bkp_name)
            (rc, out) = osubproc('rsync -a --delete-after %s %s' %
                                 (src, self.test_params['run_path']))
            gold_res = (rc == 0)

        if not gold_res:
            self.console_log("Unable to copy to %s" %
                             self.test_params['gsp_ip'])
            return False
        if len(os.listdir(app_dest_path)) == 0:
            self.console_log("Gold app folder is empty %s" % app_dest_path)
            return False


    net_params['app'] = bkp_name
    ochdir('%s/%s' % (self.test_params['run_path'], net_params['app']))
    osubproc('cp %s/Makefile .' % self.cwd)
    self.sim_out = ''
    self.soft_out = ''
    self.inp_out = ''
    with open('metadata.yaml', 'r') as fp:
        meta = yaml.load(fp, Loader=yaml.FullLoader)
    self.test_params['output_nodes'] = len(meta['out_shape'])
    for inp in range(0, int(self.test_params['output_nodes'])):
        self.sim_out = self.sim_out + 'thinciout_%s.y ' % inp
        self.soft_out = self.soft_out + 'stdout_%s.y ' % inp
    for inp in range(0, len(meta['in_shape'])):
        self.inp_out = self.inp_out + 'params_binary/input_file_%s.bin ' % inp
    return True

def run_openvx_app(self, network_name):
    self.console_log(
        "\n***************Running Openvx App for %s***************\n" %
        network_name)
    ochdir('%s/%s' %
           (self.test_params['run_path'],
            self.supported_networks[network_name]['parameters']['app']))
    out = osubproc_chkopt('make')
    if out == "output_failed":
        self.supported_networks[network_name]['result'] = 'FAILED'
        self.console_log("Sim compilation Failed for %s network" %
                         (network_name))
        return False
    self.console_log('./Release/app %s %s' % (self.inp_out, self.sim_out))
    rc, out, err = osubproc_communicate('./Release/app %s %s' %
                                        (self.inp_out, self.sim_out))
    if rc == 0:
        self.supported_networks[network_name]['siExec'] = 'PASSED'
    else:
        self.console_log(out)
        self.supported_networks[network_name]['result'] = 'FAILED'
        self.console_log("Sim Execution Failed for %s network" %
                         (network_name))
    return rc == 0


def check_si_soft(self, network_name):
    ochdir('%s/%s' %
           (self.test_params['run_path'],
            self.supported_networks[network_name]['parameters']['app']))
    run_soft = True
    gold_soft_files = glob.glob("stdout_*.y")
    if int(self.supported_networks[network_name]['parameters']
           ['use_gold_soft']) == 1:
        if len(gold_soft_files):
            run_soft = False
            self.supported_networks[network_name]['softExec'] = 'NA'
            self.console_log(
                "\n****************Checking SI, Soft Matching using gold soft******************\n"
            )
        else:
            self.console_log(
                "\n******************gold soft not available*****************\n"
            )
    if run_soft:
        self.console_log(
            "\n****************Checking SI, Soft Matching By running Softflow******************\n"
        )
        for gold_soft_file in gold_soft_files:
            os.rename(gold_soft_file, f"bkp_{gold_soft_file}")
        res = osubproc_chkopt('make soft')
        if res == "output_failed":
            self.console_log("Soft compilation Failed for %s network" %
                             (network_name))
            self.supported_networks[network_name]['result'] = 'FAILED'
            return False
        cmd = './app-soft.sh %s %s' % (self.inp_out, self.soft_out)
        self.console_log(cmd)
        soft_res = os.system(cmd)
        if soft_res == 0:
            self.supported_networks[network_name]['softExec'] = 'PASSED'
        else:
            self.console_log("Soft Execution Failed for %s network" %
                             (network_name))
            self.supported_networks[network_name]['result'] = 'FAILED'
            return False

    sim_soft_match = True
    for inp in range(0, int(self.test_params['output_nodes'])):
        sim_soft_match = sim_soft_match and self.sim_soft_checker(
            'thinciout_%s.y' % inp, 'stdout_%s.y' %
            inp, network_name)
    if sim_soft_match:
        self.console_log("Sim Soft matched for %s network" % (network_name))
        self.supported_networks[network_name]['siSoftMatch'] = 'PASSED'
    else:
        self.supported_networks[network_name]['result'] = 'FAILED'
        self.console_log("Sim Soft mismatches for %s network" % (network_name))
    return sim_soft_match


def check_randomness(self, network_name):
    if self.supported_networks[network_name][
            'siExec'] == 'FAILED' or self.supported_networks[network_name][
                'isHanging'].lower() == 'yes':
        self.console_log(
            "\nSim Execution unsucessful or Hang Detected, Performance is not applicable\n"
        )
        self.supported_networks[network_name]['result'] = 'FAILED'
        return
    print(
        "\n***************Checking Randomness for %s network***************\n"
        % network_name)
    app_name = self.supported_networks[network_name]['parameters']['app']
    print("Checking full randomness with %s times" %
          (self.test_params['randomness_count']))
    ochdir('%s/%s' % (self.test_params['run_path'], app_name))
    random_sim = ''
    random_soft = ''
    for inp in range(int(self.test_params['output_nodes'])):
        osubproc('rm -rf %s_%s' % (self.test_params['random_check_fld'], inp))
        osubproc('mkdir %s_%s' % (self.test_params['random_check_fld'], inp))
    osubproc('make si')
    for inp in range(int(self.test_params['randomness_count'])):
        random_sim = ''
        for out_nodes in range(int(self.test_params['output_nodes'])):
            random_sim = random_sim + '%s_%s/thinciout_%s.y ' % (
                self.test_params['random_check_fld'], out_nodes, inp)
        print("Running thinci flow with output %s" % random_sim)
        rc, out, err = osubproc_communicate('./Release/app %s %s' %
                                            (self.inp_out, random_sim))
        if rc == 0:
            if out.find("core hang detected in GSP") != -1:
                self.supported_networks[network_name]['isHanging'] = 'yes'
                self.console_log(
                    "Hang detected while checking randomness for openvx app")
                self.supported_networks[network_name]['result'] = 'FAILED'
                return
        else:
            print(out)
            if out.find("core hang detected in GSP") != -1:
                self.supported_networks[network_name]['isHanging'] = 'yes'
                self.console_log(
                    "Hang detected while checking randomness for openvx app")
                self.supported_networks[network_name]['result'] = 'FAILED'
                return
            self.console_log("Issue while running openvx app for randomness")
    import glob
    random_list = []
    for out_nodes in range(int(self.test_params['output_nodes'])):
        random_fld = glob.glob(
            '%s_%s/*' % (self.test_params['random_check_fld'], out_nodes))
        if len(random_fld) == 0:
            self.console_log(
                "Sim flow Output is not generated, Randomness is not applicable for %s_%s folder"
                % (self.test_params['random_check_fld'], out_nodes))
            self.supported_networks[network_name]['result'] = 'FAILED'
            continue
        ran_count, random_count, random_list = self.random_checker(random_fld)
        if ran_count == 1:
            self.console_log(
                "Randomness is observed for %s out of %s, percentage=%s for folder %s_%s"
                % (random_count, len(random_fld),
                   (float(random_count) / float(len(random_fld)) * 100),
                   self.test_params['random_check_fld'], out_nodes))
            random_list.sort()
            self.console_log(
                'Randomness is observed at below runs for folder %s_%s:\n %s' %
                (random_list, self.test_params['random_check_fld'], out_nodes))
        random_list.append(ran_count)
    if sum(random_list) == 0:
        self.console_log("No Randomness in the network")
        self.supported_networks[network_name]['randomness'] = 'no'
    else:
        self.console_log("Randomness in the network")
        self.supported_networks[network_name]['result'] = 'FAILED'


def random_checker(self, random_fld):
    inp = 1
    ran_count = 0
    random_count = 0
    random_list = []
    while inp < len(random_fld):
        rc, out, err = osubproc_communicate('diff %s %s' %
                                            (random_fld[0], random_fld[inp]))
        if rc == 0:
            if self.has_no_zeros(
                    '%s' % random_fld[0]) == 0 and self.has_no_zeros(
                        '%s' % random_fld[inp]) == 0:
                print('No Randomness for %s %s' %
                      (random_fld[0], random_fld[inp]))
            else:
                ran_count = 1
                print("Randomness zero checking failed for 'diff %s %s'" %
                      (random_fld[0], random_fld[inp]))
                random_count += 1
                random_list.append(
                    int(random_fld[inp].split('/')[-1].split('_')[-1][:-2]))
        else:
            ran_count = 1
            print("Randomness checking failed for 'diff %s %s'" %
                  (random_fld[0], random_fld[inp]))
            random_count += 1
            random_list.append(
                int(random_fld[inp].split('/')[-1].split('_')[-1][:-2]))
        inp += 1
    return ran_count, random_count, random_list


def check_performance(self, network_name, dnn_opts):
    print("N=", end='', flush=True)
    self.console_log("\n***************Checking Performance***************\n")
    app_name = self.supported_networks[network_name]['parameters']['app']
    prefer_type = ""
    if self.supported_networks[network_name]['parameters']['prefertype'] == 2:
        prefer_type = "SDK_3D_TYPE_2=1 "
    ochdir('%s/%s' % (self.test_params['run_path'], app_name))
    if os.path.exists("bkp_app"):
        osubproc('mv bkp_app app.cpp')
    osubproc('cp app.cpp bkp_app')
    osubproc(
        'rm -rf .tcdnn *.dot *.png split_before.prof savesplit_before.prof node_times.prof xyz.prof zxy.prof zxy_raster.prof vx_graph.*'
    )
    osubproc(
        'grep -irl "status |= ProcessGraph(graph);" app.cpp | xargs sed -i "s/status |= ProcessGraph(graph);/vx_uint64 ns = 0;\\nvxStartRecordingGspCoreTime(graph);\\nstatus |= ProcessGraph(graph);\\nvxStopRecordingGspCoreTime(graph,NULL);/g"'
    )
    osubproc(
        'grep -irl "int main(int argc, char \*\*argv) {" app.cpp | xargs sed -i "s/int main(int argc, char \*\*argv) {/int main(int argc, char **argv) {\\n%s/g"'
        % (dnn_opts))
    osubproc('make si')

    rc, out, err = osubproc_communicate(
        'SDK_ENABLE_NEW_EMIT_RULE=1 ' + prefer_type +
        'SDK_PROF=1 SDK_USE_PROFILER_FEEDBACK=1 SDK_RASTER=1 timeout -k 35s 35s ./Release/app %s %s'
        % (self.inp_out, self.sim_out))
    self.console_log(out)
    self.console_log(err)
    if rc != 0:
        self.console_log("Issue with Performance API")
        self.supported_networks[network_name]['result'] = 'FAILED'
        self.supported_networks[network_name]['siExec'] = 'FAILED'
        osubproc('mv bkp_app app.cpp')
        print("F[E]", end='', flush=True)
        return False

    osubproc('mv node_times.prof zxy.prof')

    rc, out, err = osubproc_communicate(
        'SDK_ENABLE_NEW_EMIT_RULE=1 ' + prefer_type +
        'SDK_PROF=1 SDK_USE_PROFILER_FEEDBACK=1 SDK_RASTER=2 timeout -k 35s 35s ./Release/app %s %s'
        % (self.inp_out, self.sim_out))
    self.console_log(out)
    self.console_log(err)
    if rc != 0:
        self.console_log("Issue with Performance API")
        self.supported_networks[network_name]['result'] = 'FAILED'
        self.supported_networks[network_name]['siExec'] = 'FAILED'
        osubproc('mv bkp_app app.cpp')
        print("F[E]", end='', flush=True)
        return False

    osubproc('mv node_times.prof xyz.prof')
    zxy = dict(line.strip().split(':') for line in open('zxy.prof'))
    xyz = dict(line.strip().split(':') for line in open('xyz.prof'))
    choosezxy = []
    for node in zxy:
        if int(zxy[node]) < int(xyz[node]):
            choosezxy.append(node)

    with open("zxy_raster.prof", "w") as outfile:
        outfile.write("\n".join(choosezxy))

    # Clear out any remaining TKOs as we cannot use profiled TKOs in performance runs
    osubproc('rm -rf .tcdnn')
    rc, out, err = osubproc_communicate(
        'SDK_ENABLE_NEW_EMIT_RULE=1 ' + prefer_type +
        'SDK_USE_PROFILER_FEEDBACK=1 timeout -k 35s 35s ./Release/app %s %s' %
        (self.inp_out, self.sim_out))
    self.console_log(out)
    self.console_log(err)
    if rc != 0:
        self.console_log("Issue with Performance API")
        self.supported_networks[network_name]['result'] = 'FAILED'
        self.supported_networks[network_name]['siExec'] = 'FAILED'
        osubproc('mv bkp_app app.cpp')
        print("F[E]", end='', flush=True)
        return False
    self.supported_networks[network_name]['siExec'] = 'PASSED'

    match = self.check_si_soft(network_name)

    self.perf_res = out
    self.console_log(self.perf_res)
    try:
        perf_stats = 0
        self.perf_res = self.perf_res.split('\n')
        self.perf_res = [x for x in self.perf_res if x]
        for inp in self.perf_res:
            if inp.find('gsp core execution time') != -1:
                perf = float(inp.split(' ')[-2])
                perf_stats = 1
        if perf_stats == 0:
            self.console_log("Issue with Performance API or app execution")
            self.supported_networks[network_name]['result'] = 'FAILED'
            osubproc('mv bkp_app app.cpp')
            print("F[S]", end='', flush=True)
            return False
    except:
        self.console_log("Issue with Performance API or app execution")
        self.supported_networks[network_name]['result'] = 'FAILED'
        osubproc('mv bkp_app app.cpp')
        print("F[S]", end='', flush=True)
        return False
    self.console_log("Performance of %s is %s fps" % (network_name, perf))
    self.supported_networks[network_name]['performance'] = str(perf)
    osubproc('mv bkp_app app.cpp')
    variance = self.supported_networks[network_name]['parameters']['variance']
    (perfcheck,
     perf_string) = compare_ref_vs_current(self.local_reference, network_name,
                                           'performance', perf, variance)
    if not perfcheck:
        self.supported_networks[network_name]['result'] = 'FAILED'
    if match:
        print("P[{}]".format(perf_string), end='', flush=True)
    else:
        print("{}[{}]".format(colored('M', 'red', attrs=['bold']),
                              perf_string),
              end='',
              flush=True)
    return perfcheck and match


def check_functionality(self, network_name):
    print("N=", end='', flush=True)
    self.console_log("\n***************Checking Performance***************\n")
    app_name = self.supported_networks[network_name]['parameters']['app']
    ochdir('%s/%s' % (self.test_params['run_path'], app_name))
    if os.path.exists("bkp_app"):
        osubproc('mv bkp_app app.cpp')
    osubproc('cp app.cpp bkp_app')
    osubproc(
        'rm -rf .tcdnn *.dot *.png split_before.prof savesplit_before.prof node_times.prof xyz.prof zxy.prof zxy_raster.prof vx_graph.*'
    )
    osubproc('make si')
    rc, out, err = osubproc_communicate('./Release/app %s %s'
        % (self.inp_out, self.sim_out))
    self.console_log(out)
    self.console_log(err)
    if rc != 0:
        self.console_log("Issue with running the app")
        self.supported_networks[network_name]['result'] = 'FAILED'
        self.supported_networks[network_name]['siExec'] = 'FAILED'
        osubproc('mv bkp_app app.cpp')
        print("F[E]", end='', flush=True)
        return False
    match = self.check_si_soft(network_name)
    return match

def sim_soft_checker(self, sim, soft, network_name):
    rc, out, err = osubproc_communicate('diff %s %s' % (sim, soft))
    if rc == 0:
        if self.has_no_zeros(sim) and self.has_no_zeros(soft):
            self.console_log("Sim and Soft Output matches for %s network" %
                             network_name)
            return True
        self.supported_networks[network_name]['result'] = 'FAILED'
        self.console_log("Soft or Sim Output has only zeroes")
        return False
    return self.check_sim_soft(sim, soft, network_name)


def has_no_zeros(self, fname):
    if os.path.isfile(fname) == False or os.stat(fname).st_size == 0:
        self.console_log("%s File doesn't exist or file contents are empty" %
                         fname)
        return False
    out = osubproc_chkopt('xxd %s' % fname, 1)
    if out == 'output_failed':
        self.console_log('Issue while executing xxd command "xxd %s"' % fname)
        return False
    out = out.split('\n')
    for line in out:
        out_line = line.split(' ')[1:-2]
        out_line = [x for x in out_line if x]
        for z in out_line:
            if z != '0000':
                return True
    if fname == 'stdout.y':
        self.console_log("Soft flow \"%s\" is dumping only zeroes" % fname)
    else:
        self.console_log("Sim flow \"%s\" is dumping only zeroes" % fname)
    return False

def uint16_packet_bfloat16_to_float32(input_val):
    import numpy as np
    input_val = np.uint16(input_val)
    sign = (input_val & (1 << 15)) >> 15
    exponent = (input_val & 0x7f80) >> 7
    mantissa = (input_val & 0x07F)
    result = pow(-1.0, sign) * pow(2.0, exponent - 127.0) * \
                (128.0 + mantissa) * pow(2.0, -7.0)
    return result

def check_sim_soft(self, sout, tout, network_name):
    if self.has_no_zeros(sout) and self.has_no_zeros(tout):
        self.console_log("Some Data is present in sim and soft")
    else:
        self.console_log(
            "Sim Soft mismatches , zero checking Failure for %s network" %
            network_name)
        return False

    if self.allow_onebit_mismatch == 0:
        return False

    net_data_type = self.supported_networks[network_name]['parameters'][
        'data_type']
    if net_data_type != 'bfloat16':
        sout = np.fromfile(sout, dtype=net_data_type)
        tout = np.fromfile(tout, dtype=net_data_type)
    else:
        import torch
        sout = np.fromfile(sout, dtype=np.int16)
        tout = np.fromfile(tout, dtype=np.int16)
        if tout.shape != sout.shape:
            self.console_log("Sim, Soft mismatches , shape checking Failure for %s network" %
            network_name)
            return False
        sout = torch.tensor(sout)
        sout_arr = uint16_packet_bfloat16_to_float32(sout)
        sout_arr = torch.tensor(sout_arr)
        sout_arr = sout_arr.float().cpu().numpy()
        tout = torch.tensor(tout)
        tout_arr = uint16_packet_bfloat16_to_float32(tout)
        tout_arr = torch.tensor(tout_arr)
        tout_arr = tout_arr.float().cpu().numpy()
        sout = sout_arr
        tout = tout_arr
    if sout.shape != tout.shape:
        self.console_log(
            "Sim Soft mismatches , shape checking Failure %s network" %
            network_name)
        return False
    diff = sout - tout
    diff = [x for x in diff if x != 0]
    if len(diff) != 0 and self.allow_onebit_mismatch == 0:
        self.console_log("Sim Soft mismatches for %s network" % network_name)
        print(diff[:100])
        return False
    diff = [x for x in diff if x < -1 or x > 1]
    if len(diff) >= 1:
        self.console_log(
            "Sim Soft mismatches , more than one bit difference Failure for %s network"
            % network_name)
        print(diff[:100])
        return False
    self.console_log("Sim Soft matches with one bit diff for %s network" %
                     network_name)
    return True


def check_pipeline_perf(self, network_name, variant, perf_result_field, opts):
    self.console_log(
        "\n\n***************Checking Performance %s for %s network ***************\n" % 
        (variant, network_name))
    cmd = "./Release/app %s" %  opts
    self.console_log(cmd)
    rc, out, err = osubproc_communicate(cmd)
    self.console_log(out)
    try:
        perf_stats = 0
        out=out.split('\n')
        out=[x for x in out if x]
        for inp in out:
            if inp.lower().find('frequency')!=-1:
                perf = round(float(inp.split('=')[-1]),2)
                perf_stats = 1
        if perf_stats == 0:
            return False
    except:
        self.console_log("Issue with Performance API")
        return False
    self.console_log("Performance of %s %s is %s fps" % (network_name, variant, perf))
    self.supported_networks[network_name][perf_result_field] = str(perf)
    return True


def run_openvx_app_pipeline(self, network_name):
    print("Functional=", end='', flush=True)
    app_name = self.supported_networks[network_name]['parameters']['app']
    ochdir('%s/%s' % (self.test_params['run_path'], app_name))
    osubproc('rm -rf output* .gpu .onnx .tcdnn')
    out = osubproc('make clean; make si')

    self.console_log(
        "\n\n***************Running app in sequential mode ***************\n")
    seq_cmd = './Release/app -s -n 20 -q 2 -o'
    rc, seqout, err = osubproc_communicate(seq_cmd)
    self.console_log(seqout)
    if rc != 0:
        self.supported_networks[network_name]['result'] = 'FAILED'
        self.supported_networks[network_name]['siExec'] = 'FAILED'
        print("sequential[{}]".format(colored('F', 'red', attrs=['bold'])), end='', flush=True)
        return False
    self.supported_networks[network_name]['siExec'] = 'PASSED'

    osubproc('rm -rf simflow_output')
    osubproc('mkdir -p simflow_output')
    osubproc('mv output*.y simflow_output/')

    self.console_log(
        "\n****************Running app in Non Pipeline mode******************\n"
    )
    nonpipelinecmd = './Release/app -d -n 20 -q 2 -o'
    self.console_log(nonpipelinecmd)
    rc, nonpipelineout, err = osubproc_communicate(nonpipelinecmd)
    self.console_log(nonpipelineout)
    if rc != 0:
        self.supported_networks[network_name]['result'] = 'FAILED'
        self.supported_networks[network_name]['softExec'] = 'FAILED'
        print("Nonpipeline[{}]".format(colored('F', 'red', attrs=['bold'])), end='', flush=True)
        return False
    self.supported_networks[network_name]['softExec'] = 'PASSED'
    osubproc('rm -rf softflow_output')
    osubproc('mkdir -p softflow_output')
    osubproc('mv output*.y softflow_output/')

    ochdir('simflow_output')
    filelist = glob.glob('*')
    ochdir('%s/%s' % (self.test_params['run_path'], app_name))
    sim_soft_match = True
    for inp in filelist:
        sim_soft_match = sim_soft_match and self.sim_soft_checker(
            'simflow_output/%s' % inp, 'softflow_output/%s' % inp,
            network_name)
    
    if sim_soft_match:
        self.console_log(
            "*************** sequential Pipeline and Non Pipeline Matches  **************"
        )
        print("{} ".format(colored('PASS', 'green')), end='', flush=True)
        self.supported_networks[network_name]['siSoftMatch'] = 'PASSED'
    else:
        self.console_log(
            "*************** sequential Pipeline and Non Pipeline MisMatches **************"
        )
        self.supported_networks[network_name]['siSoftMatch'] = 'FAILED'
        self.supported_networks[network_name]['result'] = 'FAILED'
        print("{} ".format(colored('FAIL', 'red')), end='', flush=True)
    
    num_frames = 100
    if 'frames' in self.supported_networks[network_name][
            'parameters']:
        num_frames = self.supported_networks[network_name]['parameters']['frames']

    print("Pingpong[{}]=".format(num_frames), end='', flush=True)

    variant = "pingpong"
    perf_result_field = 'pingpongPerf'
    opts = "-n %s -q 4 -g" % num_frames
    if not self.check_pipeline_perf(network_name, variant, perf_result_field, opts):
        self.console_log("Issue with pingpong Performance API or app execution")
        self.supported_networks[network_name]['result'] = 'FAILED'
        print("P[{}] ".format(colored("F", 'red', attrs=['bold'])), end='', flush=True)
        return False
    else:
        variance = self.supported_networks[network_name]['parameters']['variance']
        perf_pingpong = float(self.supported_networks[network_name][perf_result_field])
        (perfcheck, perf_string) = compare_ref_vs_current(self.local_reference, network_name,
                                           perf_result_field, 
                                           perf_pingpong, 
                                           variance)
    if not perfcheck:
        self.supported_networks[network_name]['result'] = 'FAILED'

    print("P[{}] ".format(perf_string), end='', flush=True)

    print("Sequential[{}]=".format(num_frames), end='', flush=True)

    variant = "sequential"
    perf_result_field = 'sequentialPerf'
    opts = "-n %s -q 4 -s" % num_frames
    if not self.check_pipeline_perf(network_name, variant, perf_result_field, opts):
        self.console_log("Issue with pingpong Performance API or app execution")
        self.supported_networks[network_name]['result'] = 'FAILED'
        print("P[{}]".format(colored("F", 'red', attrs=['bold'])), end='', flush=True)
        return False
    else:
        perf_seq = float(self.supported_networks[network_name][perf_result_field])
        perf_threshold = float(perf_pingpong*0.98)
        percentage = 100*(perf_seq/perf_threshold)
        if perf_seq < perf_threshold:
            self.console_log("sequential Pipeline Performance drop in %s" %
                        (network_name))
            self.supported_networks[network_name]['result'] = 'FAILED'
            print("P[{}]".format("{:.2f}:{:.2f}:{}".format(perf_threshold, perf_seq, colored("{:.1f}%".format(percentage), "red"))), end='', flush=True)
            return
        else:
            self.console_log("Expected sequential Pipeline performance reached for %s" %
                        (network_name))
            print("P[{}]".format("{:.2f}:{:.2f}:{}".format(perf_threshold, perf_seq, colored("{:.1f}%".format(percentage), "white"))), end='', flush=True)
            if perfcheck and sim_soft_match:
                self.supported_networks[network_name]['result'] = 'PASSED'
    

def run_openvx_app_customer_pipeline(self, network_name, batch_type=0):
    print("\tN=", end='', flush=True)
    self.console_log("\n***************Checking Performance***************\n")
    app_name = self.supported_networks[network_name]['parameters']['app']
    ochdir('%s/%s' % (self.test_params['run_path'], app_name))
    if os.path.exists("bkp_app"):
        osubproc('mv bkp_app app.cpp')
    osubproc('cp app.cpp bkp_app')
    osubproc('make si')
    osubproc('rm -rf .tcdnn')
    rc, out, err = osubproc_communicate(
        './Release/app %s %s' % (self.inp_out,self.sim_out))
    self.console_log(out)
    self.console_log(err)
    if rc != 0:
        self.console_log("Issue with Performance API")
        self.supported_networks[network_name]['result'] = 'FAILED'
        self.supported_networks[network_name]['siExec'] = 'FAILED'
        osubproc('mv bkp_app app.cpp')
        print("F[E]", end='', flush=True)
        return False
    out_files=[x for x in self.sim_out.split(' ') if x]
    hasZeros=False
    for inp in out_files:
        if not self.has_no_zeros(inp):
            hasZeros=True
            break
    if hasZeros:
        self.console_log("si outputs having zeros.")
        osubproc('mv bkp_app app.cpp')
        self.supported_networks[network_name]['result'] = 'FAILED'
        self.supported_networks[network_name]['siExec'] = 'FAILED'
        print("F[E]", end='', flush=True)
        return False
    self.supported_networks[network_name]['siExec'] = 'PASSED'
    self.supported_networks[network_name]['siSoftMatch'] = 'NA'
    self.supported_networks[network_name]['softExec'] = 'NA'
    self.supported_networks[network_name]['funcWithWrap'] = 'NA'
    self.supported_networks[network_name]['funcWoWrap'] = 'NA'
    self.supported_networks[network_name]['randomness'] = 'NA'

    result = re.compile(".*System FPS:.*").search(out)
    try:
        perf = float(result.group().split(":")[1].strip())
        if not perf:
            self.console_log("Issue with capture performance string")
            self.supported_networks[network_name]['result'] = 'FAILED'
            osubproc('mv bkp_app app.cpp')
            print("F[E]", end='', flush=True)
            return False
    except:
        self.console_log("Issue with capture performance string")
        self.supported_networks[network_name]['result'] = 'FAILED'
        osubproc('mv bkp_app app.cpp')
        print("F[E]", end='', flush=True)
        return False
    self.console_log("Performance of %s is %s fps" % (network_name, perf))
    self.supported_networks[network_name]['performance'] = str(perf)
    osubproc('mv bkp_app app.cpp')
    variance = self.supported_networks[network_name]['parameters']['variance']
    (perfcheck,
     perf_string) = compare_ref_vs_current(self.local_reference, network_name,
                                           'performance', perf, variance)
    print("P[{}]".format(perf_string), end='', flush=True)
    if perfcheck:
        self.supported_networks[network_name]['result'] = 'PASSED'
    else:
        self.supported_networks[network_name]['result'] = 'FAILED'


def check_stream_performance(self,
                             network_name,
                             tag,
                             variant,
                             perf_result_field,
                             func_result_field,
                             dnn_opts="",
                             extra_env=""):
    if 'nodes_to_stream' in self.supported_networks[network_name][
            'parameters']:
        extra_env += " SDK_NODES_TO_STREAM=%s" % (self.supported_networks[
            network_name]['parameters']['nodes_to_stream'])
        tag += str(self.supported_networks[network_name]['parameters']
                   ['nodes_to_stream'])

    print("S[%s]=" % tag, end='', flush=True)
    if self.supported_networks[network_name]['parameters'][variant] != 1:
        self.supported_networks[network_name][func_result_field] = 'NA'
        print("NA", end='', flush=True)
        return True
    prefer_type = ""
    if self.supported_networks[network_name]['parameters']['prefertype'] == 2:
        prefer_type = "SDK_3D_TYPE_2=1 "
    self.console_log(
        "\n***************Checking Performance %s for %s network***************\n"
        % (variant, network_name))
    app_name = self.supported_networks[network_name]['parameters']['app']
    ochdir('%s/%s' % (self.test_params['run_path'], app_name))
    if os.path.exists("bkp_app"):
        osubproc('mv bkp_app app.cpp')
    osubproc('cp app.cpp bkp_app')
    osubproc(
        'rm -rf .tcdnn *.dot *.png split_before.prof savesplit_before.prof node_times.prof vx_graph.*'
    )
    stream_out = self.sim_out
    osubproc(
        'grep -irl "status |= ProcessGraph(graph);" app.cpp | xargs sed -i "s/status |= ProcessGraph(graph);/vx_uint64 ns = 0;\\nvxStartRecordingGspCoreTime(graph);\\nstatus |= ProcessGraph(graph);\\nvxStopRecordingGspCoreTime(graph,NULL);/g"'
    )
    osubproc(
        'grep -irl "int main(int argc, char \*\*argv) {" app.cpp | xargs sed -i "s/int main(int argc, char \*\*argv) {/int main(int argc, char **argv) {\\n%s/g"'
        % (dnn_opts))
    stream_out = stream_out.replace('thinciout_', '%s_' % variant)
    osubproc('make si')

    rc, out, err = osubproc_communicate(
        'SDK_ENABLE_NEW_EMIT_RULE=1 ' + prefer_type +
        'SDK_USE_PROFILER_FEEDBACK=1 ' + extra_env +
        ' timeout -k 35s 35s ./Release/app %s %s' % (self.inp_out, stream_out))
    if rc != 0:
        self.console_log("Issue with Performance API for %s %s" %
                         (network_name, variant))
        self.supported_networks[network_name]['result'] = 'FAILED'
        self.console_log(out)
        self.console_log(err)
        osubproc('mv bkp_app app.cpp')
        print("F[E]", end='', flush=True)
        return False

    self.perf_res = out
    self.console_log(self.perf_res)
    try:
        perf_stats = 0
        self.perf_res = self.perf_res.split('\n')
        self.perf_res = [x for x in self.perf_res if x]
        for inp in self.perf_res:
            if inp.find('gsp core execution time') != -1:
                perf = float(inp.split(' ')[-2])
                perf_stats = 1
        if perf_stats == 0:
            self.console_log(
                "Issue with Performance API for %s %s or app execution" %
                (network_name, variant))
            self.supported_networks[network_name]['result'] = 'FAILED'
            osubproc('mv bkp_app app.cpp')
            print("F[S]", end='', flush=True)
            return False
    except:
        self.console_log(
            "Issue with Performance API for %s %s or app execution" %
            (network_name, variant))
        self.supported_networks[network_name]['result'] = 'FAILED'
        osubproc('mv bkp_app app.cpp')
        print("F[S]", end='', flush=True)
        return False

    self.console_log("Performance of %s %s with wrap is %s fps" %
                     (network_name, variant, perf))
    self.supported_networks[network_name][perf_result_field] = str(perf)

    osubproc('mv bkp_app app.cpp')

    sim_soft_match = True
    self.console_log(
        "\n***********************Checking %s vs Node at a time sim flow output***************************\n"
        % (variant))
    for inp in range(0, int(self.test_params['output_nodes'])):
        sim_soft_match = sim_soft_match and self.sim_soft_checker(
            '%s_%s.y' % (variant, inp), 'thinciout_%s.y' % inp, network_name)

    variance = self.supported_networks[network_name]['parameters']['variance']
    (perfcheck,
     perf_string) = compare_ref_vs_current(self.local_reference, network_name,
                                           perf_result_field, perf, variance)
    if not (perfcheck and sim_soft_match):
        self.supported_networks[network_name]['result'] = 'FAILED'
    if sim_soft_match:
        self.console_log(
            "\n***************%s Soft Matches******************\n" % (variant))
        if int(self.supported_networks[network_name]['parameters']
               ['check_randomness']) == 1:
            self.check_stream_randomness(network_name, variant,
                                         func_result_field)
        else:
            self.supported_networks[network_name][func_result_field] = 'PASSED'
        print("P[{}]".format(perf_string), end='', flush=True)
        return perfcheck
    print("{}[{}]".format(colored('M', 'red', attrs=['bold']), perf_string),
          end='',
          flush=True)
    return False


def check_stream_randomness(self, network_name, variant, func_result_field):
    if self.supported_networks[network_name][
            'siExec'] == 'FAILED' or self.supported_networks[network_name][
                'isHanging'].lower() == 'yes':
        self.console_log(
            "\nSim Execution unsucessful or Hang Detected, Performance is not applicable\n"
        )
        self.supported_networks[network_name]['result'] = 'FAILED'
        return
    print(
        "\n***************Checking %s Randomness for %s network***************\n"
        % (variant, network_name))
    app_name = self.supported_networks[network_name]['parameters']['app']
    stream_randomness_count = int(
        self.test_params['streaming_randomness_count'])
    print("Checking %s randomness with %s times" %
          (variant, stream_randomness_count))
    ochdir('%s/%s' % (self.test_params['run_path'], app_name))
    random_sim = ''
    random_soft = ''
    for inp in range(int(self.test_params['output_nodes'])):
        osubproc('rm -rf %s_%s_%s' %
                 (variant, self.test_params['random_check_fld'], inp))
        osubproc('mkdir %s_%s_%s' %
                 (variant, self.test_params['random_check_fld'], inp))
    osubproc('make si')
    for inp in range(int(stream_randomness_count)):
        random_sim = ''
        for out_nodes in range(int(self.test_params['output_nodes'])):
            random_sim = random_sim + '%s_%s_%s/thinciout_%s.y ' % (
                variant, self.test_params['random_check_fld'], out_nodes, inp)
        print("Running thinci flow with output %s" % random_sim)
        rc, out, err = osubproc_communicate('./Release/app %s %s' %
                                            (self.inp_out, random_sim))
        if rc == 0:
            if out.find("core hang detected in GSP") != -1:
                self.supported_networks[network_name]['isHanging'] = 'YES'
                self.console_log(
                    "Hang detected while checking randomness for %s openvx app"
                    % (variant))
                self.supported_networks[network_name]['result'] = 'FAILED'
                return
        else:
            print(out)
            if out.find("core hang detected in GSP") != -1:
                self.supported_networks[network_name]['isHanging'] = 'YES'
                self.console_log(
                    "Hang detected while checking randomness for %s openvx app"
                    % (variant))
                self.supported_networks[network_name]['result'] = 'FAILED'
                return
            self.console_log(
                "Issue while running openvx app for %s randomness" % (variant))
    import glob
    random_list = []
    for out_nodes in range(int(self.test_params['output_nodes'])):
        random_fld = glob.glob(
            '%s_%s_%s/*' %
            (variant, self.test_params['random_check_fld'], out_nodes))
        if len(random_fld) == 0:
            self.console_log(
                "Sim flow Output is not generated, Randomness is not applicable for %s_%s_%s folder"
                % (variant, self.test_params['random_check_fld'], out_nodes))
            self.supported_networks[network_name]['result'] = 'FAILED'
            continue
        ran_count, random_count, random_list = self.random_checker(random_fld)
        if ran_count == 1:
            self.console_log(
                "Randomness is observed for %s out of %s, percentage=%s for folder %s_%s_%s"
                % (random_count, len(random_fld),
                   (float(random_count) / float(len(random_fld)) * 100),
                   variant, self.test_params['random_check_fld'], out_nodes))
            random_list.sort()
            self.console_log(
                'Randomness is observed at below runs for folder %s_%s_%s:\n %s'
                % (random_list, variant, self.test_params['random_check_fld'],
                   out_nodes))
        random_list.append(ran_count)
    if sum(random_list) == 0:
        self.console_log("No %s Randomness in the network" % (variant))
        self.supported_networks[network_name][func_result_field] = 'PASSED'
    else:
        self.console_log("%s Randomness in the network" % (variant))


def upd_status(self, run_these_networks):
    ochdir(self.cwd)
    check_status = 1
    results = []
    yamlres = {}
    for networkname in run_these_networks:
        if self.supported_networks[networkname]['result'] == 'FAILED':
            check_status = 0
        del self.supported_networks[networkname]['parameters']
        results.append(self.supported_networks[networkname])
        yamlres[networkname] = dict(self.supported_networks[networkname])

    with open('reference.yaml', 'w') as fp:
        yaml.dump(yamlres, fp)
    data_results = pd.DataFrame(results)
    if check_status == 0:
        print(
            "\nDev Regression Failed. Please check the logs for more information. Happy Debugging"
        )
    else:
        print("\nDev Regression SUCCESSFUL.")
    #print(data_results)
    data_results.to_html(self.test_results)
    print(
        "Legend : \n  N==Node at a time, S[x] == Streaming  S[W]== Streaming wrap \n  P-Pass, F-Fail, M-Mismatch , E-Error"
    )
    print("Please check the stats at 'xdg-open %s'" % self.test_results)
    print("Please check the mini test log at 'cat test_log.txt'")
    if check_status == 0:
        sys.exit(1)
    else:
        sys.exit(0)


def test_case_picker(self):
    if type(self.network) is str and self.network == "all":
        run_these_networks = []

        for networkname in list(self.supported_networks.keys()):
            support_net_params = self.supported_networks[networkname][
                'parameters']
            if self.args.datatype and support_net_params[
                    'data_type'] != self.args.datatype:
                continue
            if self.args.variant and support_net_params[
                    'network_variant_type'] != self.args.variant:
                continue
            parms = support_net_params
            if (not parms['slow'] or parms['run_slow_tests'] == 1) and \
               (not parms['broken'] or parms['run_broken_tests'] == 1) and \
               (not parms['duplicate'] or parms['run_duplicate_tests'] == 1) and \
               (not parms['extended'] or parms['run_extended_tests'] == 1):
                run_these_networks.append(networkname)
        if not run_these_networks:
            run_these_networks = self.supported_networks.keys()
    else:
        run_these_networks = self.network
    total_networks_count = len(run_these_networks)
    count = 1
    ran_networks = []

    for networkname in run_these_networks:
        ran_networks.append(networkname)
        try:
            start_time = timeit.default_timer()
            print('[{}/{}] {}'.format(count, total_networks_count,
                                      networkname).ljust(55),
                  end='')
            self.allow_onebit_mismatch = 0
            if "yolo" in networkname or "ssd-mobilenet" in networkname or "ssd512" in networkname:
                self.allow_onebit_mismatch = 1

            if not self.copy_app_from_remote_to_local(networkname):
                self.supported_networks[networkname]['result'] = 'NA'
                count += 1
                continue

            if int(self.supported_networks[networkname]['parameters']
                   ['run_tests']) == 1:

                if not 'pipeline' in self.supported_networks[networkname]['parameters']['network_variant_type']:
                    if int(self.supported_networks[networkname]['parameters']
                           ['check_randomness']) == 1:
                        self.check_randomness(networkname)
                    elif int(self.supported_networks[networkname]['parameters']
                           ['check_functionality']) == 1:
                        run_frequency = self.supported_networks[networkname]['parameters'].get('run_frequency')
                        if run_frequency == 'daily':
                            self.check_functionality(networkname)
                    else:
                        self.supported_networks[networkname][
                            'randomness'] = 'NA'
                    dnn_opts = "tcdnn::configuration.enable_streaming = 0;\\n" +\
                            "tcdnn::configuration.enable_buffer_wrap = 0;\\n"
                    self.check_performance(networkname, dnn_opts)
                    print(" ", end='')

                    tag = "x"
                    variant = "streamwowrap"
                    perf_result_field = 'streamPerfWoWrap'
                    func_result_field = 'funcWoWrap'
                    dnn_opts = "tcdnn::configuration.enable_streaming = 1;\\n" +\
                            "tcdnn::configuration.enable_buffer_wrap = 0;\\n"
                    self.check_stream_performance(networkname, tag, variant,
                                                  perf_result_field,
                                                  func_result_field, dnn_opts)
                    print(" ", end='')

                    tag = "W"
                    variant = "streamwwrap"
                    perf_result_field = 'streamPerfWithWrap'
                    func_result_field = 'funcWithWrap'
                    dnn_opts = "tcdnn::configuration.enable_streaming = 1;\\n" +\
                            "tcdnn::configuration.enable_buffer_wrap = 1;\\n"
                    self.check_stream_performance(networkname, tag, variant,
                                                  perf_result_field,
                                                  func_result_field, dnn_opts)

                    #self.check_stream_performance(networkname, "WA", variant, perf_result_field, func_result_field, dnn_opts, extra_env="SDK_NODES_TO_STREAM=10000")
                    #print(" ", end='')
                    #self.check_stream_performance(networkname,1,1, extra_env="SDK_NODES_TO_STREAM=1000")
                elif 'pipeline' == self.supported_networks[networkname]['parameters']['network_variant_type']:
                    self.run_openvx_app_customer_pipeline(networkname)
                else:
                    self.run_openvx_app_pipeline(networkname)
            elapsed = timeit.default_timer() - start_time
            print("  ({:0.3f} sec)".format(elapsed))
            if self.supported_networks[networkname]['result'] == 'FAILED':
                self.console_log(
                    '\n**********Network=%s FAILED************\n' %
                    networkname)
                if self.test_params['early_exit_failure']:
                    break
            else:
                self.console_log(
                    '\n**********Network=%s SUCCESSFULL***********\n' %
                    networkname)
            count += 1
        except KeyboardInterrupt:
            ran_networks.remove(networkname)
            break
    self.upd_status(ran_networks)


def console_log(self, message):
    if self.test_params['verbose'] == 1:
        print(message)


class run_dev_regressions:
    def __init__(self):
        self.cwd = os.getcwd()
        self.network_metadata_file = 'network_metadata.json'
        self.neworks_data = {}
        self.supported_networks = OrderedDict()
        self.config_file = 'config.json'
        self.test_params = {}
        self.gold_app_name = 'gold_app'
        self.sdk_env = ['PREFIX_DIR', 'LD_LIBRARY_PATH']
        self.home_location = os.path.expanduser('~')
        self.initialize_parameters()
        self.test_results = 'results_regressions.html'
        self.fp = open('test_log.txt', 'w')

    parse_arguments = parse_arguments
    get_network_dump = get_network_dump
    read_network_dump = read_network_dump
    mount_apps = mount_apps
    initialize_parameters = initialize_parameters
    check_env = check_env
    test_case_picker = test_case_picker
    copy_app_from_remote_to_local = copy_app_from_remote_to_local
    run_openvx_app = run_openvx_app
    run_openvx_app_pipeline = run_openvx_app_pipeline
    run_openvx_app_customer_pipeline = run_openvx_app_customer_pipeline
    check_si_soft = check_si_soft
    check_performance = check_performance
    check_pipeline_perf = check_pipeline_perf
    check_stream_performance = check_stream_performance
    has_no_zeros = has_no_zeros
    check_sim_soft = check_sim_soft
    sim_soft_checker = sim_soft_checker
    check_randomness = check_randomness
    print_log = print_log
    upd_status = upd_status
    random_checker = random_checker
    check_stream_randomness = check_stream_randomness
    console_log = console_log
    copy_app_from_to_bkp_srv = copy_app_from_to_bkp_srv
    connect_paramiko = connect_paramiko



def main():
    reg = run_dev_regressions()
    reg.test_case_picker()


if __name__ == '__main__':
    main()

