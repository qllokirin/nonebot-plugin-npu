rs6_id = "_rs6_id_"
rs6_content = "_rs6_content_"

delete __dirname
delete __filename

delete process
function watch(obj, name) {
    return new Proxy(obj, {
        get: function (target, property, receiver) {
            try {
                if (typeof target[property] === "function") {
                    //console.log("对象 => " + name + ",读取属性:" + property + ",值为:" + 'function' + ",类型为:" + (typeof target[property]))
                } else {
                    //console.log("对象 => " + name + ",读取属性:" + property + ",值为:" + target[property] + ",类型为:" + (typeof target[property]))
                }
            } catch (e) {
            }
            return target[property]
        },
        set: (target, property, newValue, receiver) => {
            try {
                //console.log("对象 => " + name + ",设置属性:" + property + ",值为:" + newValue + ",类型为:" + (typeof newValue))
            } catch (e) {
            }
            return Reflect.set(target, property, newValue, receiver)
        }
    })
}

window = global;
window.top = window;
window.location = {
    "ancestorOrigins": {},
    "href": "https://jwxt.nwpu.edu.cn/student/sso-login",
    "origin": "https://jwxt.nwpu.edu.cn",
    "protocol": "https:",
    "host": "jwxt.nwpu.edu.cn",
    "hostname": "jwxt.nwpu.edu.cn",
    "port": "",
    "pathname": "/student/sso-login",
    "search": "",
    "hash": ""
}
window.XMLHttpRequest = function (args) {
    //console.log("对象 => window,方法 => XMLHttpRequest,参数为:" + args)
}
window.localStorage = {
}
window.addEventListener = function (args) {
    //console.log("对象 => window,方法 => addEventListener,参数为:" + args)
}
window.setTimeout = function () { }
window.setInterval = function () { }
window.navigator = {
}

// window = watch(global, 'window')

div = {
    getElementsByTagName: function (args) {
        //console.log("对象 => div,方法 => getElementsByTagName,参数为:" + args)
        if (args === 'i') {
            return []
        }
    }
}

meta = [
    watch({}, 'meta1'),
    watch({
        id: rs6_id,
        content: rs6_content,
        getAttribute: function (args) {
            //console.log("对象 => meta,方法 => getAttribute,参数为:" + args)
            if (args === 'r') {
                return 'm'
            }
        },
        parentNode: function (args) {
            //console.log("对象 => meta,方法 => parentNode,参数为:" + args)
        },
        parentNode: {
            removeChild: function (args) {
                //console.log("对象 => meta.parentNode,方法 => removeChild,参数为:" + args)
            }
        }
    }, 'meta2')]
script = [
    watch({
        src: '',
        getAttribute: function (args) {
            //console.log("对象 => script,方法 => getAttribute,参数为:" + args)
            if (args === 'r') {
                return 'm'
            }
        },
        parentElement: {
            removeChild: function (args) {
                //console.log("对象 => script.parentElement,方法 => removeChild,参数为:" + args)
            }
        }
    }, 'script1'),
    watch({
        getAttribute: function (args) {
            //console.log("对象 => script,方法 => getAttribute,参数为:" + args)
            if (args === 'r') {
                return 'm'
            }
        },
        parentElement: {
            removeChild: function (args) {
                //console.log("对象 => script.parentElement,方法 => removeChild,参数为:" + args)
            }
        },
    }, 'script2')
]
document = {
    createElement: function (args) {
        //console.log("对象 => document,方法 => createElement,参数为:" + args)
        if (args === 'div') {
            aaa = watch(div, 'div')
            return aaa
        }
    },
    appendChild: function (args) {
        //console.log("对象 => document,方法 => appendChild,参数为:" + args)
    },
    removeChild: function (args) {
        //console.log("对象 => document,方法 => removeChild,参数为:" + args)
    },
    getElementById: function (args) {
        //console.log("对象 => document,方法 => getElementById,参数为:" + args)
        if (args === 'hK5iNqnNcwxO') {
            return meta[1]
        }
    },
    getElementsByTagName: function (args) {
        //console.log("对象 => document,方法 => getElementsByTagName,参数为:" + args)
        if (args === 'base') {
            return []
        }
        if (args === 'meta') {
            bbb = watch(meta, 'meta')
            return bbb
        }
        if (args === 'script') {
            ccc = watch(script, 'script')
            return ccc
        }
    },
    addEventListener: function (args) {
        //console.log("对象 => document,方法 => addEventListener,参数为:" + args)
    }
}
// document = watch(document,'document')