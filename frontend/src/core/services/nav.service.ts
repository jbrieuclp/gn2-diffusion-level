import { Injectable, OnInit } from '@angular/core';
import { Subject } from 'rxjs/Subject';

@Injectable()
export class NavService {
    // Observable string sources
    private _appName = new Subject<string>();
    gettingAppName = this._appName.asObservable();
    // List of the apps
    private _nav = [{}];
    constructor() {
        this._nav = [{route: '/home', appName: 'Accueil', icon: 'home'},
            {route: '/synthese', appName: 'Synthèse', icon: 'device_hub'},
            {route: '/contact', appName: 'Contact FF', icon: 'visibility'},
            {route: '/map-list', appName: 'Dev Map List', icon: 'build'},
            {route: '/flore-station', appName: 'Flore Station', icon: 'local_florist'},
            {route: '/suivi-flore', appName: 'Suivi Flore', icon: 'filter_vintage'},
            {route: '/suivi-chiro', appName: 'Suivi Chiro', icon: 'youtube_searched_for'},
            {route: '/exports', appName: 'Exports', icon: 'cloud_download'},
            {route: '/prospections', appName: 'Prospections', icon: 'feedback'},
            {route: '/parametres', appName: 'Paramètres', icon: 'settings'}
            ];
  }

    setAppName(appName: string): any {
      this._appName.next(appName);
    }

    getAppList(): any {
      return this._nav;
    }
}
