
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
