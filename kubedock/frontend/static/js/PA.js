(function(){
    'use strict';
    window.PA = function(options){
        var app = this;
        app.defaultKubeType = options.defaultKubeType || 0;
        app.userPackage = options.userPackage;
        app.template = options.template;

        app.kubesByID = {};
        app.userPackage.kubes.forEach(function(kube){ app.kubesByID[kube.id] = kube; });

        var filled = jsyaml.safeLoad(app.fill());
        this.hasPublicPorts = anyPublicPorts(app.getSpec(filled));
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

    PA.autogen = function(){
        var s = [(~~(11 + Math.random() * 25)).toString(36)],  // first letter
            len = 7;
        while(len--)
            s.push((~~(Math.random() * 36)).toString(36));
        return s.join('');
    };

    //                          ---name---       ------default------      ---title---
    PA.FIELD_PATTERN = /[^\\](\$([^\|\$\\]+)(?:\|default:([^\|\$\\]+)(?:\|([^\|\$\\]+))?)?\$)/g;

    PA.prototype.getSpec = function(yml){
        yml = yml || this.fill();
        return (yml.spec.template || yml).spec;
    };

    PA.prototype.getFields = function(){
        var fields = [], match;
        fields.byName = Object.create(null);
        while ((match = PA.FIELD_PATTERN.exec(this.template)) !== null){
            var text = match[1],
                name = match[2],
                value = match[3],
                title = match[4],
                hidden = false,
                field;
            if (value === 'autogen'){
                value = PA.autogen();
                hidden = true;
            } else if (value && value.toLowerCase() === 'user_domain_list'){
                value = text;
                hidden = true;
            }
            if (name in fields.byName){
                field = fields.byName[name];
                field.occurrences.push(text);
                if (field.value === undefined)  // $VAR_NAME$ was before full definition
                    field.value = value; field.title = title; field.hidden = hidden;
            } else {
                field = {title: title, value: value, name: name,
                         hidden: hidden, occurrences: [text]};
                fields.push(field);
                fields.byName[name] = field;
            }
        }
        return fields;
    };

    PA.prototype.fill = function(values){
        values = values || {};

        var fields = this.getFields(),
            template = this.template;
        fields.forEach(function(field){
            var value = values[field.name] !== undefined ? values[field.name] : field.value;
            field.occurrences.forEach(function(text){
                template = template.replace(text, value);
            });
        });
        return template;
    };

    PA.prototype.fillAppPackageWithDefaults = function(appPackage, pod){
        var full = JSON.parse(JSON.stringify(appPackage));  // deep copy
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

        var names = (spec.volumes || []).map(function(v){ return v.name; });
        fullPod.persistentDisks.forEach(function(pd){
            pd.pdSize = pd.pdSize || 1;
            names.splice(names.indexOf(pd.name), 1);
        });
        names.forEach(function(name){
            fullPod.persistentDisks.push({name: name, pdSize: 1});
        });
        return full;
    };

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

    PA.prototype.applyAppPackage = function(pod, appPackage){
        var podPlan = appPackage.pods[0],
            spec = this.getSpec(pod);

        pod.kuberdock.kube_type = podPlan.kubeType;

        var kubesByContainerName = {};
        podPlan.containers.forEach(
            function(c){ kubesByContainerName[c.name] = c.kubes; });
        spec.containers.forEach(
            function(c){ c.kubes = kubesByContainerName[c.name]; });

        var pdByVolumeName = {};
        podPlan.persistentDisks.forEach(
            function(pd){ pdByVolumeName[pd.name] = pd.pdSize; });
        (spec.volumes || []).forEach(
            function(vol){ vol.persistentDisk.pdSize = pdByVolumeName[vol.name]; });

        if (appPackage.publicIP === false && this.hasPublicPorts){
            spec.containers.forEach(function(c){ c.ports.forEach(
                function(port){ port.isPublic = false; });
            });
        }
        return pod;
    };

    PA.prototype.templateToApp = function(appPackageID, values){
        var filled = jsyaml.safeLoad(this.fill(values)),
            appPackage = filled.kuberdock.appPackages[appPackageID];
        appPackage = this.fillAppPackageWithDefaults(appPackage, filled);
        delete filled.kuberdock.appPackages;
        return this.applyAppPackage(filled, appPackage);
    };

})();
