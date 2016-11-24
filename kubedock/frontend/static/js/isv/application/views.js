// import App from 'isv/app';
// import * as Model from 'isv/model';
import * as utils from 'app_data/utils';
import detailsTpl from './templates/details.tpl';

// import 'bootstrap-editable';
// import 'jqplot';
// import 'jqplot-axis-renderer';
// import 'bootstrap-select';
// import 'tooltip';


export const Details = Marionette.ItemView.extend({
    template: detailsTpl,
    onBeforeShow: utils.preloader2.show,
    onShow: utils.preloader2.hide,
    modelEvents: {
        change: 'render',
    },

    templateHelpers(){
        return {
            appLastUpdate: utils.localizeDatetime({
                dt: this.model.get('appLastUpdate'),
                formatString: 'YYYY-MM-DD HH:mm:ss (z)',
            }),
        };
    },
});
