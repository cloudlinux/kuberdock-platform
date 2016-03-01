(function(){
    'use strict';
    /**
     * Tool for parsing and filling Predefined Apps templates
     *
     * @class PA
     * @param {Object} options - Options to initialize
     *   @param {Object} options.template - yaml template
     *   @param {number} [options.defaultKubeType=0]
     *   @param {Object} options.userPackage - Object, describing user's package
     *      (GET /api/pricing/packages/<id>?with_kubes=true)
     */
    var PA = function(options){
        var app = this;
        app.defaultKubeType = options.defaultKubeType || 0;
        app.userPackage = options.userPackage;
        app.kubesByID = {};
        app.userPackage.kubes.forEach(function(kube){ app.kubesByID[kube.id] = kube; });

        // original template
        app.rawTemplate = options.template;

        var result = app.preprocess();
        // $VARIABLES$ -> uid; unescape escaped $
        app.preparedTemplate = result.template;
        app.fields = result.fields;

        app.loadedTemplate = app.load();

        result = app.fill();
        app.filledDefault = result.filledTemplate;  // filled with default values
        app.fields = result.usedFields;  // only fields needed to fill the template

        app.hasPublicPorts = anyPublicPorts(app.getSpec());
    };


    /**
     * Used to represent each unique variable in template
     * @class TemplateField
     * @param {{name: string, value: string, label: string}} options -
     *      info from full field definition
     */
    var TemplateField = function(options){
        this.name = options.name;
        this.uid = PA.autogen(32);

        if (options.value !== undefined)  // full definition
            this.setup(options);
    };
    /**
     * Use it if full field definition (with label and default) was met after
     * the short ($VAR$).
     * @param {{value: string, label: string}} options -
     *      info from full field definition
     */
    TemplateField.prototype.setup = function(options){
        this.value = TemplateField.unescape(options.value);
        this.label = TemplateField.unescape(options.label);

        if (this.value === 'autogen'){
            this.hidden = true;
            this.type = 'str';
            this.value = PA.autogen();
        } else {
            this.hidden = false;
            this.type = TemplateField.getType(this.value);
            this.value = jsyaml.safeLoad(this.value);
        }
        this.defined = true;
    };
    // Coerce value to the type of this field
    TemplateField.prototype.coerce = function(value){
        if (value === undefined)
            return this.value;  // default

        if (this.type === 'bool'){
            if (typeof value == 'string')
                return value.strip().toLowerCase() === 'true';
            return !!value;
        }
        if (this.type === 'int')
            return (typeof value == 'string' ? parseFloat(value) : +value) | 0;
        if (this.type === 'float')
            return (typeof value == 'string' ? parseFloat(value) : +value);
        return value.toString();
    };

    // Static Methods:

    // Unescape default value or label (\. -> .)
    TemplateField.unescape = function(value){
        return value.replace(/\\([\s\S])/g, '$1');
    };
    /**
     * Choose yaml-tag for specified value.
     * @param {string} value - plain yaml-scalar
     * @return {string} one of: bool, int, float, timestamp, str
     */
    TemplateField.getType = function(value){
        // get type of value, based on yaml resolving
        var types = jsyaml.DEFAULT_SAFE_SCHEMA.compiledTypeMap,
            tags = ['bool', 'int', 'float', 'str'];

        for (var i = 0; i < tags.length; i++) {
            var tag = tags[i], type = types['tag:yaml.org,2002:' + tag];
            if (type.resolve && type.resolve(value))
                return tag;  // tag:yaml.org,2002:float -> float
        }
    };

    function anyPublicPorts(pod){
        var containers = pod.containers;
        for (var i = containers.length; i--;){
            var ports = containers[i].ports || [];
            for (var j = ports.length; j--;)
                if (ports[j].isPublic)
                    return true;
        }
        return false;
    }

    /**
     * Generate a random sequence of alphanumeric symbols
     * (lowercase, first is always a letter).
     * @param {number} [len=8]
     * @return {string} random string
     */
    PA.autogen = function(len){
        len = (len || 8) - 1;  // 8 by default, including first letter
        var s = [(~~(10 + Math.random() * 26)).toString(36)];  // first letter
        while(len--)
            s.push((~~(Math.random() * 36)).toString(36));  // [0-9a-z]
        return s.join('');
    };


    PA.prototype.getSpec = function(yml){
        yml = yml || this.filledDefault;
        return (yml.spec.template || yml).spec;
    };


    /* CoffeeScript:
        FIELD_PARSER = ///
            \$(?:              # match $$ (escaped $) or $VAR[|default:<>|Label]$
                ([\w\-]+)      # name: alphanumeric, -, _
                (?:\|default:  # default and label: any symbol except \,|,$; or any escaped symbol
                    ((?:[^\\\|\$]|\\[\s\S])+|)
                    \|
                    ((?:[^\\\|\$]|\\[\s\S])+|)
                )?             # default and label are optioanl
            )?\$
        ///g;
    */
    PA.FIELD_PARSER = /\$(?:([\w\-]+)(?:\|default:((?:[^\\\|\$]|\\[\s\S])+|)\|((?:[^\\\|\$]|\\[\s\S])+|))?)?\$/g;

    /**
     * Find all field definitions and prepare yaml for loading:
     * replace fields with UIDs and unescape $ ($$->$).
     *
     * @param  {string} [target=PA#rawTemplate]
     * @return {{template: string, fields: TemplateField[]}}
     *      template prepared for loading and list of parsed fields
     */
    PA.prototype.preprocess = function(target){
        target = target || this.rawTemplate;
        var fields = [], field;
        fields.byName = {};
        fields.byUID = {};

        // replace all escaped $$ with $ and all $fields$ with UIDs
        target = target.replace(PA.FIELD_PARSER, function(match, name, value, label) {
            if (match === '$$')  // escaped
                return '$';    // unescape

            if (name in fields.byName){  // have met it before
                field = fields.byName[name];
                if (value !== undefined){
                    if (field.defined){
                        console.warn(  // eslint-disable-line no-console
                            'Second definition of the same variable: ' + name);
                    } else {
                        field.setup({value: value, label: label});
                    }
                }
            } else {  // first appearing of this field
                field = new TemplateField({name: name, value: value, label: label});
                fields.push(field);
                fields.byName[name] = field;
                fields.byUID[field.uid] = field;
            }

            // replace with unique aplphanum string
            // it's unique enough to say that collision won't apper ever
            return field.uid;
        });

        // check for $VAR$ without full definition ($VAR|default:...$)
        for (var name in fields.byName){
            if (!fields.byName[name].defined)
                console.warn(  // eslint-disable-line no-console
                    'Undefined variable: ' + name);
        }

        return {template: target, fields: fields};
    };


    /**
     * Parse YAML, converting plain $variables$ to links to TemplateField objects
     *
     * @param  {string} [target=PA#preparedTemplate] - prepared template
     * @return {Object} loaded template
     */
    PA.prototype.load = function(target){
        if (target === undefined) target = this.preparedTemplate;
        var app = this;

        var TemplateFieldTag = new jsyaml.Type('kd', {
            kind: 'scalar',
            // check if YAML node should be converted to this type
            resolve: function(data){ return data in app.fields.byUID; },
            // construct JS object from YAML node
            construct: function (data) { return app.fields.byUID[data]; },
        });
        var SCHEMA = new jsyaml.Schema({include: [jsyaml.DEFAULT_SAFE_SCHEMA],
                                        implicit: [TemplateFieldTag]});
        return jsyaml.safeLoad(target, {schema: SCHEMA});
    };


    /**
     * Replace all TemplateField instancies and fields inside strings with values.
     *
     * @param  {Object} [values=fieldsDefaults]
     * @param  {Object} [target=PA#loadedTemplate] - loaded template to fill
     * @return {Object} filled template and fields that was used
     *      (fields that are really presented in the target)
     */
    PA.prototype.fill = function(values, target){
        if (values === undefined) values = {};
        if (target === undefined) target = this.loadedTemplate;
        var app = this;

        var used = {};
        var fillNode = function(node){  // recursively fill all nested nodes
            if (node instanceof TemplateField){
                used[node.name] = true;
                node = node.coerce(values[node.name]);
            } else if (typeof node == 'string'){
                for (var uid in app.fields.byUID){
                    var field = app.fields.byUID[uid];
                    node = node.replace(uid, function(){
                        used[field.name] = true;
                        return field.coerce(values[field.name]);
                    });
                }
            } else if (node !== null && typeof node == "object") {
                var newObject = node instanceof Array ? [] : {},
                    key, value;
                for (key in node) {
                    value = fillNode(node[key]);
                    key = fillNode(key);
                    newObject[key] = value;
                }
                node = newObject;
            }
            return node;
        };

        var filledTemplate = fillNode(this.loadedTemplate),
            usedFields = [];
        usedFields.byName = new Object(null);
        usedFields.byUID = new Object(null);

        for (var name in used){
            var field = this.fields.byName[name];
            usedFields.push(field);
            usedFields.byName[name] = usedFields.byUID[field.uid] = field;
        }

        return {filledTemplate: filledTemplate, usedFields: usedFields};
    };


    // Add default values for kubesQTY, pdSize and other stuff in appPackage (in-place)
    PA.prototype.fillAppPackageWithDefaults = function(appPackage, pod){
        var full = appPackage;
        full.goodFor = full.goodFor || '';
        full.publicIP = full.publicIP !== false;
        full.pods = full.pods && full.pods.length ? full.pods : [{}];

        var fullPod = full.pods[0];
        fullPod.kubeType = fullPod.kubeType === undefined ?
            this.defaultKubeType : fullPod.kubeType;
        fullPod.name = pod.metadata.name;
        fullPod.containers = fullPod.containers || [];
        fullPod.persistentDisks = fullPod.persistentDisks || [];

        var spec = this.getSpec(pod);
        var names = spec.containers.map(function(c){ return c.name; });
        fullPod.containers.forEach(function(c){
            c.kubes = c.kubes || 1;
            names.splice(names.indexOf(c.name), 1);
        });
        names.forEach(function(name){
            fullPod.containers.push({name: name, kubes: 1});
        });

        names = [];
        (spec.volumes || []).forEach(function(volume){
            if (volume.persistentDisk)
                names.push(volume.name);
        });
        fullPod.persistentDisks.forEach(function(pd){
            pd.pdSize = pd.pdSize || 1;
            names.splice(names.indexOf(pd.name), 1);
        });
        names.forEach(function(name){
            fullPod.persistentDisks.push({name: name, pdSize: 1});
        });
        return full;
    };

    // Get main info about package: resources, price, preiod
    PA.prototype.calculateInfo = function(appPackage){
        var result = {};

        var pod = appPackage.pods[0],
            space = String.fromCharCode(160);
        result.totalKubes = pod.containers.reduce(
            function(sum, c){ return sum + (+c.kubes); }, 0);
        result.totalPD = pod.persistentDisks.reduce(
            function(sum, pd){ return sum + (+pd.pdSize); }, 0);
        result.publicIP = appPackage.publicIP && this.hasPublicPorts;
        result.kubeType = this.kubesByID[pod.kubeType];

        var kt = result.kubeType;
        result.print = {};
        result.cpu = result.totalKubes * kt.cpu;
        result.memory = result.totalKubes * kt.memory;
        result.diskSpace = result.totalKubes * kt.disk_space;
        result.price = (kt.price * result.totalKubes +
                        this.userPackage.price_pstorage * result.totalPD +
                        this.userPackage.price_ip * (+result.publicIP));
        result.print = {
            cpu: result.cpu.toFixed(2) + space + kt.cpu_units,
            memory: Math.round(result.memory) + space + kt.memory_units,
            diskSpace: Math.round(result.diskSpace) + space + kt.disk_space_units,
            pd: result.totalPD + space + 'GB',
            period: this.userPackage.period,
            price: {
                full: this.userPackage.prefix + space + result.price.toFixed(2) +
                    space + this.userPackage.suffix,
                prefix: this.userPackage.prefix,
                suffix: this.userPackage.suffix,
                value: result.price,
            },
        };
        return result;
    };

    // Pass package configuration in pod's spec
    PA.prototype.applyAppPackage = function(pod, appPackage){
        var podPlan = appPackage.pods[0],
            spec = this.getSpec(pod),
            kuberdock = pod.kuberdock;

        pod.kuberdock.kube_type = podPlan.kubeType;

        var kubesByContainerName = {};
        podPlan.containers.forEach(
            function(c){ kubesByContainerName[c.name] = c.kubes; });
        spec.containers.forEach(
            function(c){ c.kubes = kubesByContainerName[c.name]; });

        var pdByVolumeName = {};
        podPlan.persistentDisks.forEach(
            function(pd){ pdByVolumeName[pd.name] = pd.pdSize; });
        (spec.volumes || []).forEach(function(vol){
            if (vol.persistentDisk)
                vol.persistentDisk.pdSize = pdByVolumeName[vol.name];
        });

        if (appPackage.publicIP === false && this.hasPublicPorts){
            spec.containers.forEach(function(c){ c.ports.forEach(
                function(port){ port.isPublic = false; });
            });
        }

        if (appPackage.packagePostDescription){
            kuberdock.postDescription += '\n' + appPackage.packagePostDescription;
        }
        return pod;
    };

    /**
     * Will return yaml, filled with provided values and appPackage applied.
     *
     * @param {number} appPackageID - package index
     * @param {Object} values - see PA#fill
     * @returns {Object} filled template with appPackage applied
     */
    PA.prototype.templateToApp = function(appPackageID, values){
        var filled = this.fill(values).filledTemplate,
            appPackage = filled.kuberdock.appPackages[appPackageID];
        this.fillAppPackageWithDefaults(appPackage, filled);
        delete filled.kuberdock.appPackages;
        return this.applyAppPackage(filled, appPackage);
    };

    window.PA = PA;

})();
