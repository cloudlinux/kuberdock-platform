*** Settings ***
Documentation     A test suite containing tests with billing.

Force Tags        billing

Resource          whmcs_admin_resource.robot
Resource          global_resources.robot

Suite Setup       Open KuberDock Admin's Browser
Suite Teardown    Close All Browsers

Test Teardown     Close All Error Messages
