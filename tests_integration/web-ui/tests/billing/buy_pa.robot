*** Settings ***
Documentation     File with steps for "Buy PA with billing" tests
...              (https://cloudlinux.testrail.net/index.php?/cases/view/189)


Resource          global_resources.robot
Resource          ./whmcs_admin_resource.robot
Resource          ./whmcs_user_resource.robot
Resource          ./kd_admin_resource.robot
Resource          ./kd_user_resource.robot
Resource          ../billing/price_calculation.robot
Resource          ../ip_pool/resource.robot
Resource          ../pods/resource.robot
Resource          ../users/resource.robot

Library           Dialogs

Suite Teardown    Close All Browsers
Test Setup        Login into the KuberDock


*** Variables ***
${WHMCS SERVER}                       whmcs.some.com
${WHMCS URL}                          http://${WHMCS SERVER}
${WHMCS ADMIN URL}                    http://${WHMCS SERVER}/admin
${WHMCS LOGIN}                        admin
${WHMCS PASSWORD}                     some_password3
${SECRET KEY}                         some_secret
${APP NAME}                           Dokuwiki
${TESTED APP PACKAGE}                 M
${BILLING TYPE}                       Fixed Price
${KD SSH LOGIN}                       root
${KD SSH PASSWORD}                    some_password2
${WHMCS SERVER HOSTNAME}              192.168.33.74
${WHMCS SSH LOGIN}                    root
${WHMCS SSH PASSWORD}                 some_password
${WHMCS PATH}                         /home/whmcs/public_html


*** Keywords ***
Delete Tested Data
    Delete Pod On Pod Info Page
    Close Browser
    Switch Browser  KuberDockAdmin
    Delete Test's IP Pool
    Close Browser
    Switch Browser  WHMCSadmin
    Delete WHMCS User


*** Test Cases ***
Buy PA With Fixed Price Settings and zero balance
    Synchronize Server Time On KD and WHMCS
    # Configure KuberDock
    Select KD settings to use WHMCS billing  ${WHMCS URL}  ${WHMCS LOGIN}  ${WHMCS PASSWORD}
    Add IP pool
    # Go to WHMCS Admin side
    Open WHMCS Admin's Browser
    Login WHMCS admin
    # Confiruge Standart Package prices
    Configire WHMCS Package
    ...  package type=Standard package
    ...  billing type=Fixed price
    ...  ip_price=2.00
    ...  ps_price=10.00
    ...  action=as soon as an order is placed  # When pay for invoice
    ...  tiny=10.00  standard=20.00  high_memory=30.00
    # Standard package should not take Trial price
    Configire WHMCS Package
    ...  package type=Trial
    ...  billing type=PAYG
    ...  ip_price=6.00
    ...  ps_price=7.00
    ...  action=as soon as an order is placed  # When pay for invoice
    ...  tiny=1000.00  standard=2000.00  high_memory=3000.00
    # Purchase of PA
    Switch Browser  KuberDockAdmin
    Generate PA Order Page Link
    Get "${APP NAME}" Prices
    Try To Buy PA Package and Check Prices  ${TESTED APP PACKAGE}  ${APPLICATION S AP_PACKAGE PRICE}
    ...  ${APPLICATION L AP_PACKAGE PRICE}   ${APPLICATION M AP_PACKAGE PRICE}
    Make Check in WHMCS  New User  UNPAID
    Switch Browser  WHMCSadmin
    Add Money To WHMCS User Account For Buy Pod
    Switch Browser  KuberDockUser
    Pay For Invoice
    Check That Pod is Running
    Change WHMCS Server Time to 1 Month and 5 Days Forward and Run Cron Script
    Pod Should Be Unpaid
    Container Should Be Stoped
    Switch Browser  KuberDockAdmin
    Check User Status  ${user email address}  Active
    Switch Browser  WHMCSadmin
    Check New Invoice  Unpaid
    Mark Invoice As Paid
    Switch Browser  KuberDockUser
    Check That Pod is Running
    [Teardown]  Delete Tested Data
