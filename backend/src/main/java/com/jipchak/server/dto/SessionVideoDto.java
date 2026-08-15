package com.jipchak.server.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SessionVideoDto {
    private String id;
    private String url;
    private String thumb;
    private Boolean isSuccess;
}
