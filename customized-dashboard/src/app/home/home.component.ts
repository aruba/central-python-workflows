import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { AppService } from '../app.service';

@Component({
    selector: 'home',
    templateUrl: './home.component.html'
})
export class HomeComponent implements OnInit {

    constructor(private router: Router, private appService: AppService) {}

    ngOnInit() {
        if (this.appService.getStoredJson())
            this.router.navigate(['dashboard']);
    }

    customizeDashboard() {
        this.router.navigate(['selectWidgets']);
    }
}
