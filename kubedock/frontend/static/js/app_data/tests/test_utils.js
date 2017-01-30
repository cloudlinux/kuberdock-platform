/*
 * KuberDock - is a platform that allows users to run applications using Docker
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


/**
 * Extract and fix references to imported modules, so you can spy/stub/mock them using sinon.
 *
 * It's necessary in case of namespace-import, like
 * ```
 * import * as blahblah from 'blahblah';
 * ```
 * and practical in some other cases.
 *
 * If you need to completely replace some module, use `__set__` or `__with__` directly.
 */
export const rewired = function(RewireAPI, ...modules) {
    var original = {};

    for (let name of modules){
        original[name] = RewireAPI.__get__(name);
        RewireAPI.__Rewire__(name, original[name]);
    }
    return [
        original,
        () => modules.forEach((name) => RewireAPI.__ResetDependency__(name)),
    ];
};
