/* * KuberDock - is a platform that allows users to run applications using Docker
 * container images and create SaaS / PaaS based on these applications.
 * Copyright (C) 2017 Cloud Linux INC
 *
 * This file is part of KuberDock.
 *
 * KuberDock is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * KuberDock is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with KuberDock; if not, see <http://www.gnu.org/licenses/>.
 */

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>


int main(int argc, char **argv) {
   char uid[256];
   char * eargv[9];
   snprintf(uid, 256, "%d", getuid());
   eargv[0]=HOOKEXEC;   /* executable path */
   eargv[1]="--token";
   eargv[2]=argv[1];    /* token */
   eargv[3]="kubectl";
   eargv[4]="postprocess";
   eargv[5]=argv[2];    /* pod name */
   eargv[6]="--uid";
   eargv[7]=uid;        /* uid */
   eargv[8]=NULL;
   setuid(0);
   execv(eargv[0], eargv);
   return 0;
}