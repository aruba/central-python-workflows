import { Component, OnInit, ViewEncapsulation } from '@angular/core';
import { AppService } from './app.service';
import { Router } from '@angular/router';
import { HttpManager } from 'central-ui-core';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
  encapsulation: ViewEncapsulation.None
})

export class AppComponent implements OnInit {
  title = 'customized-dashboard';

  constructor(private appService: AppService, private _router: Router, private _httpManager: HttpManager) {}
  ngOnInit() {
    setInterval(()=> {
      this._httpManager.get('refresh_token').subscribe(resp => {})
    }, 15 * 60 * 1000)
  }

  showDashboard() {
    if (this.appService.getStoredJson())
      this._router.navigate(['dashboard']);
    else
      this._router.navigate(['home']);
  }

  logout() {
    this._httpManager.get('logout').subscribe(resp => {
      window.location.href = '/';
    }, error => {
      window.location.href = '/';
    })
  }
}
