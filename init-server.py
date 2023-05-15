#!/usr/bin/python3
import re
import subprocess
import time
from datetime import date
import os
import shutil

print("Running...")


def main():
    # ================================================================================
    # Variables
    name = get_container_name()
    domain: list = get_domain()
    port: str = get_port()
    email: str = get_email()
    staging: str = "--staging" if 'y' == input('Is it for testing or not? [y/n]: ').lower() else ""
    # ================================================================================
    # Start preparing configs
    print("Preparing env file...")
    prepare_env_file(domain, port)
    print('Done')

    print("Preparing docker-compose configuration...")
    prepare_docker_compose_yml_before_start(name, domain, port)
    print('Done')

    print("Preparing entrypoint file...")
    prepare_letsencrypt_initialize_script(domain, staging, email)
    print('Done')

    os.mkdir('./sites-available')
    os.mkdir('./sites-enabled')

    # ================================================================================
    # Running container
    print('Creating container {} ....'.format(name))
    subprocess.run(['docker-compose', 'up', '-d', '--build'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if not subprocess.run(['docker', 'exec', '-d', name, './letsencrypt-initialize.py'],
                          stdout=subprocess.PIPE).returncode:
        prepare_docker_compose_yml_after_start()
        prepare_app_conf_template(domain)
        time.sleep(10)
        print('Done')
        print("Installation has finished! Congratulations!")
        print("You have successfully enabled https://{}".format(domain[0]))
        subprocess.run(['docker', 'cp', "{}:/etc/nginx/conf.d/default.conf".format(name),
                        './sites-available/{}.conf'.format(domain[0])], stdout=subprocess.PIPE)
        collect_garbage()
        os.remove('./init-server.py')
    else:
        print('Error with obtaining TLS certificate!')
        exit(1)


def collect_garbage():
    """Collect unused files and directories"""
    os.remove('./.env')
    os.remove('./letsencrypt-initialize.py')
    shutil.rmtree("./templates")


def prepare_app_conf_template(domain: list):
    """Function to prepare template to run nginx as a reverse proxy to any application"""
    with open('templates/nginx_templates/app.conf', 'r') as f:
        template = f.read()

    template = template.replace('$domain_single', domain[0].strip())
    template = template.replace('$domain', ' '.join(domain).strip())

    with open('./sites-available/{}_app.conf'.format(domain[0]), 'w') as f:
        f.write(template)


def get_port() -> str:
    """Function to get port number from user or set to default 80"""
    for i in range(3):
        port = input('Please, enter a port [1-65535] that you want to run a webserver(if you want '
                     'to use the default just skip this step with press Enter): \n')
        if port:
            if check_port(port):
                return port
        else:
            return "80"
    print("Error")
    exit(1)


def check_port(input_str: str) -> bool:
    """Port validator"""
    regex = \
        r"^((6553[0-5])|(655[0-2][0-9])|(65[0-4][0-9]{2})|(6[0-4][0-9]{3})|([1-5][0-9]{4})|([0-5]{0,5})|([0-9]{1,4}))$"
    pattern = re.compile(regex)
    if not pattern.search(input_str):
        return False
    return True


def get_container_name() -> str:
    """Function to get preferred name of container or set to default nginx_{date.today()}"""
    name = input(
        'Please, enter a container name '
        '(you can skip this step and the script will name the container automatically): \n')
    if not name:
        name = "nginx_{}".format(date.today())
    return name


def prepare_docker_compose_yml_after_start():
    """Function uncomment entrypoint arg in docker-compose.yml for the successfully created container"""
    with open('docker-compose.yml', 'r') as f:
        old_data = f.read()

    new_data = old_data.replace('    #entrypoint', '    entrypoint')
    new_data = new_data.replace('    env_file:', '')
    new_data = new_data.replace('      - .env', '')
    new_data = new_data.replace('      - ./templates/nginx_templates:/etc/nginx/templates', '')

    with open('docker-compose.yml', 'w') as f:
        f.write(new_data)


def prepare_docker_compose_yml_before_start(name: str, domain: list, port: str):
    """Function prepare docker-compose.yml from docker-compose.yml.template with replacing env variables"""
    with open('./templates/docker-compose.yml.template', 'r') as f:
        old_data = f.read()

    new_data = old_data.replace('$name', name)
    new_data = new_data.replace('$port', port)
    new_data = new_data.replace('$domain', domain[0])

    with open('docker-compose.yml', 'w') as f:
        f.write(new_data)


def prepare_env_file(domain: list, port: str):
    """Function prepare env variables"""
    with open('./templates/.env.template', 'r') as f:
        old_data = f.read()

    new_data = old_data.replace('$nginx_host', ' '.join(domain))
    new_data = new_data.replace('$nginx_port', port)
    new_data = new_data.replace('$nginx_log_name', domain[0])

    with open('.env', 'w') as f:
        f.write(new_data)


def prepare_letsencrypt_initialize_script(domain: list, staging: str, email: str):
    """
    Function prepare letsencrypt-initialize.py from
    letsencrypt-initialize.py.template with replacing env variables
    """
    with open('./templates/letsencrypt-initialize.py.template', 'r') as f:
        old_data = f.read()

    new_data = old_data.replace('$staging_arg', staging)

    if email == "--register-unsafely-without-email":
        new_data = new_data.replace('$email_arg', email)
    else:
        new_data = new_data.replace('$email_arg', "--email " + email)
    new_data = new_data.replace('$domain', '-d ' + ' -d '.join(domain))
    new_data = new_data.replace('$conf', domain[0])

    # Deleting a surplus whitespaces
    while "  " in new_data:
        new_data = new_data.replace("  ", " ")

    with open('./letsencrypt-initialize.py', 'w') as f:
        f.write(new_data)


def get_domain() -> list:
    """
    Request to enter domain name(s) from the user
    The function can return either nip.io domain names or the custom ones entered by the user
    """
    for i in range(3):
        domain: list = list(map(lambda x: x.strip(),
                                input(
                                    "Please, enter your domain and subdomain(if exists) with "
                                    "whitespace as separator: \n"
                                    "(If you don`t have any domain you can enter your public "
                                    "IP or just skip this step and script "
                                    "will do all things automatically)\n").split()))
        # If nothing entered we`re going to get ip address and convert it in valid domain name with nip.io
        if not domain:
            return get_nip_io_domain(domain)
        # Checking, if the inputted data is an ip address, we`ll compiling domain with nip.io
        if not check_is_ip(domain):
            if check_domain(domain):
                return domain
        else:
            return get_nip_io_domain(domain)
    print("Error")
    exit(1)


def check_domain(domain: list) -> bool:
    """Validate domain name(s)"""
    regex = r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$"
    pattern = re.compile(regex)
    # Loop through all entered domains
    for domain in domain:
        if not pattern.search(domain):
            print('You have entered invalid domain {}'.format(domain))
            return False
    return True


def check_is_ip(domain_lst: list) -> bool:
    """Validate ip"""
    regex = r"((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)"
    pattern = re.compile(regex)
    for domain in domain_lst:
        if not pattern.search(domain):
            return False
    return True


def get_nip_io_domain(domain: list) -> list:
    """
    If no domain is passed, the function will request an ip address and prepare nip.io with the received ip, otherwise
    the function will prepare with domain that is passed in args
    """
    if not domain:
        domain = [subprocess.run(['curl', '-s', '2ip.ru'], stdout=subprocess.PIPE, text=True).stdout.strip()]
    first_domain = "{}.nip.io".format(domain[0])
    second_domain = "www.{}.nip.io".format(domain[0])
    return [first_domain, second_domain]


def check_email(input_str: str) -> str:
    """Validate email"""
    regex = r'^[-\w.]+@([A-z0-9][-A-z0-9]+\.)+[A-z]{2,4}$'
    pattern = re.compile(regex)
    if pattern.search(input_str):
        return input_str
    else:
        return ""


def get_email():
    """Request to enter email from the user"""
    for i in range(3):
        input_str = input("Please, enter your email(strongly recommended), if you don`t want, press Enter: \n").strip()
        if input_str:
            result = check_email(input_str.strip())
            if result:
                return result
        else:
            return "--register-unsafely-without-email"
    print("Error")
    exit(1)


if __name__ == '__main__':
    main()
